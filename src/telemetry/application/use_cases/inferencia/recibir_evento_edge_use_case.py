# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-10-20 | Arekkazu | DEV-29 RF-56: rechaza dispositivo o sensor inactivos (401)      |
# | 2026-10-21 | Arekkazu | DEV-45 RF-56: E1 rechazo temporal en bitácora, E6 límite por dispositivo, E7 intento no autorizado |
# | 2026-10-21 | Leandro | DEV-49 RF-57: conecta bitacora al procesamiento Edge |
# | 2026-10-25 | Arekkazu | INC-M03-137-G179 RF-63: emite DESVIACION_DETECTADA / EVENTO_COMPUESTO_GENERADO |
# | 2026-10-26 | Leandro | INC-M03-110-G42 RF-55/RF-56: rechaza orden temporal invertido y devuelve la captura original. |
# | 2026-10-26 | destroyerban | INC-M03-111-G43 RF-55.1: guarda valor y umbrales aplicados por el Edge |
# | 2026-10-27 | destroyerban | INC-M03-118-G61 RF-55: latencia de deteccion medida en el Edge y SLA de 500 ms |
# | 2026-10-27 | destroyerban | INC-M03-121-G64 RF-56 E6: límite de eventos por dispositivo configurable por entorno |
# | 2026-10-28 | destroyerban | INC-M03-199-G54 RF-55: trazabilidad de la regla (regla_aplicada, nombre_regla, version_regla) |
# | 2026-10-28 | Arekkazu | BE-2/BE-3 RF-55: id_regla_alerta en el evento y regla aplicada en la alerta |
from __future__ import annotations

import logging
import os

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.shared.errors import AuthenticationError, ValidationError
from src.shared.rate_limit import registrar_llamada
from src.telemetry.application.use_cases.alertas.generar_alerta_use_case import GenararAlertaUseCase
from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import RegistrarEventoAuditoriaIotUseCase
from src.telemetry.domain.entities.alerta import ReglaAlerta, regla_edge
from src.telemetry.domain.entities.evento_auditoria_iot import ComponenteOrigen, SeveridadLog, TipoResultado
from src.telemetry.application.use_cases.inferencia.consolidar_paquete_inferencia_use_case import (
    ConsolidarEnviarPaqueteUseCase,
)
from src.telemetry.application.use_cases.inferencia.registrar_rechazo_evento_edge import (
    registrar_evento_rechazado,
    registrar_intento_no_autorizado,
)
from src.telemetry.domain.repositories.bitacora_auditoria_iot_repository import BitacoraAuditoriaIotRepository
from src.telemetry.domain.entities.telemetria import (
    LATENCIA_MAX_MS_RF55,
    CAMPOS_TRAZABILIDAD_REGLA,
    EventoEdgeComputing,
    ResultadoEventoEdge,
    TipoEventoEdge,
    clasificacion_a_tipo_evento_bd,
    latencia_edge_ms,
)
from src.telemetry.domain.repositories.dispositivo_port import DispositivoPort
from src.telemetry.domain.repositories.evento_edge_repository import EventoEdgeRepository
from src.telemetry.domain.repositories.motor_inferencia_port import MotorInferenciaPort
from src.telemetry.domain.repositories.paquete_inferencia_repository import PaqueteInferenciaRepository
from src.telemetry.domain.repositories.parametros_alertas_port import ParametrosAlertasPort
from src.telemetry.domain.repositories.regla_alerta_repository import ReglaAlertaRepository
from src.telemetry.infrastructure.dto.procesar_evento_alerta_dto import ProcesarEventoAlertaDTO
from src.telemetry.infrastructure.dto.recibir_evento_edge_dto import RecibirEventoEdgeDTO
from src.telemetry.infrastructure.repositories.alerta_repository import SqlAlchemyAlertaRepository
from src.telemetry.infrastructure.repositories.historico_estado_alerta_repository import SqlAlchemyHistoricoEstadoAlertaRepository
from src.telemetry.infrastructure.repositories.regla_alerta_repository import SqlAlchemyReglaAlertaRepository

_MAX_DRIFT_FUTURO_SEG = 30
_MAX_VENTANA_BUFFER_HORAS = 72
# RF-56 E6: eventos por minuto y por dispositivo; los CRITICO no cuentan (se priorizan).
# ponytail: contador en memoria por proceso (src/shared/rate_limit.py); compartido si hay réplicas.
# G64: el RF no fija la cifra; 60 es la propuesta de DEV-45, ajustable sin código por entorno.
LIMITE_EVENTOS_POR_MINUTO = 60
_ENV_LIMITE_EVENTOS = "IOT_EVENTOS_EDGE_LIMITE_POR_MINUTO"
_MAX_INT4 = 2**31 - 1
logger = logging.getLogger(__name__)

# RF-63: tipo de evento de la bitácora para cada desviación que reporta RF-55.
_EVENTO_BITACORA_RF55 = {
    TipoEventoEdge.DESVIACION_SIMPLE: "DESVIACION_DETECTADA",
    TipoEventoEdge.DESVIACION_COMPUESTA: "EVENTO_COMPUESTO_GENERADO",
}


def _limite_eventos_por_minuto() -> int:
    valor = os.environ.get(_ENV_LIMITE_EVENTOS, "").strip()
    if not valor:
        return LIMITE_EVENTOS_POR_MINUTO
    try:
        limite = int(valor)
    except ValueError:
        limite = 0
    if limite <= 0:
        logger.warning("RF-56 E6: %s=%r no es un entero positivo; se usa %d.",
                       _ENV_LIMITE_EVENTOS, valor, LIMITE_EVENTOS_POR_MINUTO)
        return LIMITE_EVENTOS_POR_MINUTO
    return limite
def _trazabilidad_completa(metadatos: dict) -> bool:
    return all(metadatos.get(campo) is not None for campo in CAMPOS_TRAZABILIDAD_REGLA)


class RecibirEventoEdgeUseCase:

    def __init__(
        self,
        db: Session,
        evento_edge_repo: EventoEdgeRepository,
        paquete_repo: PaqueteInferenciaRepository,
        dispositivo_port: DispositivoPort,
        motor_inferencia_port: MotorInferenciaPort,
        parametros_alertas_port: ParametrosAlertasPort,
        auditoria_repo: Optional[BitacoraAuditoriaIotRepository] = None,
        regla_repo: Optional[ReglaAlertaRepository] = None,
    ) -> None:
        self.db = db
        self.evento_edge_repo = evento_edge_repo
        self.paquete_repo = paquete_repo
        self.dispositivo_port = dispositivo_port
        self.motor_inferencia_port = motor_inferencia_port
        self.parametros_alertas_port = parametros_alertas_port
        self.auditoria_repo = auditoria_repo
        self.regla_repo = regla_repo

    def execute(
        self,
        dto: RecibirEventoEdgeDTO,
        gateway_id: Optional[str] = None,
    ) -> ResultadoEventoEdge:
        ahora = datetime.now(timezone.utc)
        ts_captura = dto.timestamp_captura
        if ts_captura.tzinfo is None:
            ts_captura = ts_captura.replace(tzinfo=timezone.utc)
        ts_procesamiento = dto.timestamp_procesamiento_edge
        if ts_procesamiento.tzinfo is None:
            ts_procesamiento = ts_procesamiento.replace(tzinfo=timezone.utc)

        # E6: control de tasa por dispositivo; un evento CRITICO nunca se frena.
        if dto.severidad != "CRITICO":
            registrar_llamada(f"rf56_eventos_edge:{dto.serial}", _limite_eventos_por_minuto(), 60)

        # Paso 1: Validar coherencia temporal (E1: el rechazo queda en bitácora con el evento)
        try:
            self._validar_temporal(ts_captura, ts_procesamiento, ahora, dto.origen)
        except ValidationError as exc:
            if self.auditoria_repo is not None:
                registrar_evento_rechazado(self.db, self.auditoria_repo, motivo=exc.message, codigo=exc.code,
                                           payload=dto.model_dump(mode="json"), serial=dto.serial)
            raise

        # Paso 2: Validar identidad del dispositivo
        dispositivo = self.dispositivo_port.obtener_dispositivo_activo(
            dto.device_id, dto.sensor_id, dto.serial
        )
        if dispositivo is None or not dispositivo.es_activo_dispositivo or not dispositivo.es_activo_sensor:
            if self.auditoria_repo is not None:  # E7
                registrar_intento_no_autorizado(self.db, self.auditoria_repo, codigo="DISPOSITIVO_NO_AUTORIZADO",
                                                serial=dto.serial, device_id=dto.device_id)
            raise AuthenticationError(
                code="DISPOSITIVO_NO_AUTORIZADO",
                message="El dispositivo o el sensor no corresponden al serial, o están inactivos.",
            )

        tipo_evento_bd = clasificacion_a_tipo_evento_bd(dto.clasificacion_rf55)
        # INC-M03-118-G61: evidencia del SLA de RF-55 por evento. Si el Edge enviara estas
        # claves en metadata_edge, prevalece el cálculo del backend sobre sus propios timestamps.
        latencia = latencia_edge_ms(ts_captura, ts_procesamiento)
        sla_excedido = latencia > LATENCIA_MAX_MS_RF55
        metadatos = {**self._metadatos_evento(dto), "latencia_edge_ms": latencia, "sla_edge_excedido": sla_excedido}
        regla = self._regla_existente(dto.metadata_edge)

        evento = EventoEdgeComputing(
            id_dispositivo_iot=dispositivo.id_dispositivo_iot,
            id_sensor=dispositivo.id_sensor,
            clasificacion_rf55=dto.clasificacion_rf55,
            tipo_evento=tipo_evento_bd,
            severidad=dto.severidad,
            # mode='json' asegura serialización compatible (Decimal→str, datetime→str)
            variables_involucradas=[v.model_dump(mode='json') for v in dto.variables_involucradas],
            fecha_captura=ts_captura,
            fecha_procesamiento=ts_procesamiento,
            origen_dato=dto.origen,
            estado_conectividad=dto.estado_conectividad,
            valor_evaluado=dto.valor_evaluado,
            umbral_min_aplicado=dto.umbral_min_aplicado,
            umbral_max_aplicado=dto.umbral_max_aplicado,
            metadatos=metadatos,
            id_regla_alerta=regla.id_regla_alertas if regla else None,
        )

        # Paso 3-4: Guardar evento
        try:
            evento_guardado = self.evento_edge_repo.guardar(evento)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        tipo_bitacora = _EVENTO_BITACORA_RF55.get(dto.clasificacion_rf55)
        if tipo_bitacora and self.auditoria_repo is not None:
            RegistrarEventoAuditoriaIotUseCase(self.db, self.auditoria_repo).execute(
                tipo_evento=tipo_bitacora,
                resultado=TipoResultado.EXITOSO,
                componente_origen=ComponenteOrigen.RF55,
                severidad_log=SeveridadLog.WARNING,
                descripcion=f"Desviación {dto.clasificacion_rf55} detectada en el Edge.",
                accion_detallada={
                    "id_evento_edge_computing": evento_guardado.id_evento_edge_computing,
                    "id_dispositivo_iot": dispositivo.id_dispositivo_iot,
                    "id_sensor": dispositivo.id_sensor,
                    "severidad": dto.severidad,
                    "variables": [v.tipo_variable for v in dto.variables_involucradas],
                },
                fecha_evento=ts_procesamiento,
            )

        # Paso 5: Consolidar y enviar a M04 si hay desviación (fuera del bloque DB anterior)
        # ERROR_CONFIGURACION: evento guardado pero no se envía a M04 (FA-07)
        paquete = None
        paquete_estado: Optional[str] = None
        _enviar_a_m04 = dto.clasificacion_rf55 not in (TipoEventoEdge.NORMAL, TipoEventoEdge.ERROR_CONFIGURACION)
        if _enviar_a_m04:
            consolidar = ConsolidarEnviarPaqueteUseCase(
                db=self.db,
                paquete_repo=self.paquete_repo,
                motor_inferencia_port=self.motor_inferencia_port,
                auditoria_repo=self.auditoria_repo,
            )
            paquete = consolidar.execute(evento_guardado)
            if paquete:
                paquete_estado = paquete.estado_paquete

        # Paso 6: Generar alerta si hay desviación (best-effort — no propaga error)
        _es_desviacion = dto.clasificacion_rf55 in (
            TipoEventoEdge.DESVIACION_SIMPLE,
            TipoEventoEdge.DESVIACION_COMPUESTA,
        )
        if _es_desviacion and dto.variables_involucradas and dto.severidad:
            self._generar_alerta_best_effort(
                dto=dto,
                dispositivo_id_iot=dispositivo.id_dispositivo_iot,
                id_infraestructura=dispositivo.id_infraestructura,
                id_evento_edge=evento_guardado.id_evento_edge_computing,
                id_paquete=paquete.id_paquetes_inferencia if paquete else None,
                regla=regla,
            )

        return ResultadoEventoEdge(
            id_evento_edge_computing=evento_guardado.id_evento_edge_computing,
            clasificacion_rf55=evento_guardado.clasificacion_rf55,
            severidad=evento_guardado.severidad,
            estado_conectividad=evento_guardado.estado_conectividad,
            fecha_captura=evento_guardado.fecha_captura,
            fecha_procesamiento=evento_guardado.fecha_procesamiento,
            paquete_inferencia_estado=paquete_estado,
            valor_evaluado=evento_guardado.valor_evaluado,
            umbral_min_aplicado=evento_guardado.umbral_min_aplicado,
            umbral_max_aplicado=evento_guardado.umbral_max_aplicado,
            latencia_edge_ms=latencia,
            sla_edge_excedido=sla_excedido,
        )

    def _generar_alerta_best_effort(
        self,
        dto: RecibirEventoEdgeDTO,
        dispositivo_id_iot: int,
        id_infraestructura: Optional[int],
        id_evento_edge: int,
        id_paquete: Optional[int],
        regla: Optional[ReglaAlerta] = None,
    ) -> None:
        try:
            var_primaria = dto.variables_involucradas[0]
            alerta_dto = ProcesarEventoAlertaDTO(
                device_id=dto.device_id,
                sensor_id=dto.sensor_id,
                serial=dto.serial,
                tipo_variable=var_primaria.tipo_variable,
                valor=var_primaria.valor,
                unidad=var_primaria.unidad,
                timestamp_evento=dto.timestamp_captura,
                estado_dato="LECTURA_VALIDA",
                severidad_edge=dto.severidad,
                origen_evento="EDGE",
                id_evento_edge_computing=id_evento_edge,
                id_paquete_inferencia=id_paquete,
                reglas_activadas=[regla_edge(dto.clasificacion_rf55, dto.metadata_edge, regla, var_primaria.tipo_variable)],
                metadata_evento=dto.metadata_edge,
            )
            GenararAlertaUseCase(
                db=self.db,
                alerta_repo=SqlAlchemyAlertaRepository(self.db),
                historico_repo=SqlAlchemyHistoricoEstadoAlertaRepository(self.db),
                regla_repo=SqlAlchemyReglaAlertaRepository(self.db),
                parametros_port=self.parametros_alertas_port,
                auditoria_repo=self.auditoria_repo,
            ).execute(
                dto=alerta_dto,
                id_dispositivo_ioit=dispositivo_id_iot,
                id_infraestructura=id_infraestructura,
            )
        except Exception:
            self.db.rollback()
            logger.warning("RF-57: no se pudo generar la alerta del evento Edge %s.", id_evento_edge)

    def _regla_existente(self, metadata_edge: Optional[dict]) -> Optional[ReglaAlerta]:
        """BE-2: ``metadata_edge.id_regla_alerta`` solo si la regla existe (la columna tiene FK:
        un id que mandó el Edge y no existe haría perder el evento)."""
        id_regla = (metadata_edge or {}).get("id_regla_alerta")
        if self.regla_repo is None or isinstance(id_regla, bool) or not isinstance(id_regla, int):
            return None
        if not 0 < id_regla <= _MAX_INT4:  # fuera de integer, la consulta misma fallaría
            return None
        return self.regla_repo.obtener_por_id(id_regla)

    @staticmethod
    def _metadatos_evento(dto: RecibirEventoEdgeDTO) -> dict:
        """metadata_edge tal como la emitió el nodo; en un evento compuesto, marca si trae la regla (G54)."""
        metadatos = dict(dto.metadata_edge or {})
        if dto.clasificacion_rf55 == TipoEventoEdge.DESVIACION_COMPUESTA:
            metadatos["trazabilidad_regla_completa"] = _trazabilidad_completa(metadatos)
        return metadatos

    @staticmethod
    def _validar_temporal(
        ts_captura: datetime, ts_procesamiento: datetime, ahora: datetime, origen: str,
    ) -> None:
        delta = (ts_captura - ahora).total_seconds()
        if delta > _MAX_DRIFT_FUTURO_SEG:
            raise ValidationError(
                code="TIMESTAMP_FUTURO",
                message=f"El timestamp de captura está {delta:.0f} s en el futuro (máx. {_MAX_DRIFT_FUTURO_SEG} s).",
                field="timestamp_captura",
            )
        if origen == "BUFFER_LOCAL":
            antiguedad = (ahora - ts_captura).total_seconds() / 3600
            if antiguedad > _MAX_VENTANA_BUFFER_HORAS:
                raise ValidationError(
                    code="TIMESTAMP_EXPIRADO",
                    message=f"El dato de buffer tiene {antiguedad:.1f} h de antigüedad (máx. {_MAX_VENTANA_BUFFER_HORAS} h).",
                    field="timestamp_captura",
                )
        # RF-55 CA-13: la igualdad es válida cuando el reloj tiene precisión limitada.
        if ts_procesamiento < ts_captura:
            raise ValidationError(
                code="ORDEN_TEMPORAL_INVALIDO",
                message="El timestamp de procesamiento Edge no puede ser anterior al de captura.",
                field="timestamp_procesamiento_edge",
            )

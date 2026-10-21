# | Fecha      | Nombre  | Que se hizo                                           |
# |------------|---------|-------------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-49 RF-57: registra diagnostico real de fallo motor |
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session
from src.shared.errors import ServiceUnavailableError
from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import RegistrarEventoAuditoriaIotUseCase
from src.telemetry.domain.entities.evento_auditoria_iot import ComponenteOrigen, EntidadAfectadaTipo, SeveridadLog, TipoResultado
from src.telemetry.domain.repositories.bitacora_auditoria_iot_repository import BitacoraAuditoriaIotRepository

from src.shared.errors import BusinessRuleError
from src.telemetry.domain.entities.telemetria import (
    EstadoCalidadBitacora,
    EstadoCalidadTelemetria,
    EstadoPaqueteInferencia,
    EventoEdgeComputing,
    PaqueteInferencia,
    TipoEventoEdge,
)
from src.telemetry.domain.repositories.motor_inferencia_port import MotorInferenciaNoIntegradoError, MotorInferenciaPort
from src.telemetry.domain.repositories.paquete_inferencia_repository import PaqueteInferenciaRepository

logger = logging.getLogger(__name__)

# Variables mínimas por categoría para contexto completo
_MINIMOS_AMBIENTAL = {"TEMPERATURA_AMBIENTAL", "HUMEDAD_RELATIVA"}
_MINIMOS_ANIMAL = {"TEMPERATURA_CORPORAL", "TEMP_CORPORAL", "FRECUENCIA_CARDIACA"}
_MINIMOS_HIDRICA = {"PH_AGUA", "OXIGENO_DISUELTO"}

_CATEGORIA_VARIABLE: dict[str, str] = {
    "TEMPERATURA_AMBIENTAL": "AMBIENTAL",
    "HUMEDAD_RELATIVA": "AMBIENTAL",
    "NH3": "AMBIENTAL",
    "CO2": "AMBIENTAL",
    "TEMPERATURA_CORPORAL": "ANIMAL",
    "TEMP_CORPORAL": "ANIMAL",
    "FRECUENCIA_CARDIACA": "ANIMAL",
    "FRECUENCIA_RESPIRATORIA": "ANIMAL",
    "ACTIVIDAD_MOVIMIENTO": "ANIMAL",
    "ACTIVIDAD": "ANIMAL",
    "PH_AGUA": "HIDRICA",
    "OXIGENO_DISUELTO": "HIDRICA",
    "TDS": "HIDRICA",
    "CONDUCTIVIDAD_ELECTRICA": "HIDRICA",
}


def _evaluar_contexto(variables: list[dict]) -> tuple[dict, bool]:
    """Agrupa variables por categoría y determina si el contexto es completo."""
    por_categoria: dict[str, list[dict]] = {"AMBIENTAL": [], "ANIMAL": [], "HIDRICA": []}
    tipos_presentes: set[str] = set()

    for v in variables:
        tipo = v.get("tipo_variable", "")
        cat = _CATEGORIA_VARIABLE.get(tipo, "AMBIENTAL")
        por_categoria[cat].append(v)
        tipos_presentes.add(tipo)

    # Una categoría se considera completa si tiene sus variables mínimas
    categorias_activas = {cat for cat, vars in por_categoria.items() if vars}
    incompleto = False

    for cat in categorias_activas:
        if cat == "AMBIENTAL" and not (_MINIMOS_AMBIENTAL <= tipos_presentes):
            incompleto = True
        elif cat == "ANIMAL":
            tiene_temp = bool({"TEMPERATURA_CORPORAL", "TEMP_CORPORAL"} & tipos_presentes)
            tiene_fc = "FRECUENCIA_CARDIACA" in tipos_presentes
            if not (tiene_temp and tiene_fc):
                incompleto = True
        elif cat == "HIDRICA" and not (_MINIMOS_HIDRICA <= tipos_presentes):
            incompleto = True

    contexto = {cat: vars for cat, vars in por_categoria.items() if vars}
    return contexto, incompleto


class ConsolidarEnviarPaqueteUseCase:

    def __init__(
        self,
        db: Session,
        paquete_repo: PaqueteInferenciaRepository,
        motor_inferencia_port: MotorInferenciaPort,
        auditoria_repo: BitacoraAuditoriaIotRepository | None = None,
    ) -> None:
        self.db = db
        self.paquete_repo = paquete_repo
        self.motor_inferencia_port = motor_inferencia_port
        self.auditoria_repo = auditoria_repo

    def execute(self, evento: EventoEdgeComputing) -> Optional[PaqueteInferencia]:
        """
        RF-56 pasos 7-10: consolidar paquete multivariable y enviar a M04.
        Solo se ejecuta si clasificacion_rf55 != NORMAL.
        Devuelve None si no hay nada que enviar.
        """
        if evento.clasificacion_rf55 == TipoEventoEdge.NORMAL:
            return None

        variables = evento.variables_involucradas
        if not variables:
            raise BusinessRuleError(
                code="PAQUETE_INCONSISTENTE",
                message="El evento Edge no contiene variables para consolidar.",
            )

        # FA-03: validar que el evento tiene al menos una variable con valor
        variable_principal = variables[0]
        tipo_variable = variable_principal.get("tipo_variable")
        valor_raw = variable_principal.get("valor")
        if not tipo_variable or valor_raw is None:
            raise BusinessRuleError(
                code="PAQUETE_INCONSISTENTE",
                message="La variable principal del evento no tiene tipo_variable o valor.",
            )

        # Paso 7: Consolidar contexto multivariable
        contexto_ambiental, contexto_incompleto = _evaluar_contexto(variables)

        # Paso 8: Validar consistencia (FA-03)
        self._validar_timestamps(variables)

        valor_numerico = Decimal(str(valor_raw))
        unidad = variable_principal.get("unidad")

        metadatos = {
            "timestamp_captura": evento.fecha_captura.isoformat(),
            "timestamp_procesamiento_edge": evento.fecha_procesamiento.isoformat(),
            "clasificacion_rf55": evento.clasificacion_rf55,
        }

        paquete = PaqueteInferencia(
            id_sensor=evento.id_sensor,
            id_dispositivo_iot=evento.id_dispositivo_iot,
            id_evento_edge_computing=evento.id_evento_edge_computing,
            tipo_variable=tipo_variable,
            valor_numerico=valor_numerico,
            unidad=unidad,
            estado_calidad=EstadoCalidadTelemetria.LECTURA_VALIDA,
            estado_desviacion=evento.clasificacion_rf55,
            severidad=evento.severidad,
            origen=evento.origen_dato,
            contexto_ambiental=contexto_ambiental,
            contexto_incompleto=contexto_incompleto,
            metadatos=metadatos,
            fecha_envio=datetime.now(timezone.utc),
            estado_paquete=EstadoPaqueteInferencia.PENDIENTE,
            intento_envios=0,
        )

        try:
            existente = self.paquete_repo.obtener_por_evento(
                evento.id_evento_edge_computing, bloquear_evento=True,
            )
            if existente is not None:
                # Reconsolidar no es reenviar: conserva el mismo ID y estado.
                self.db.commit()
                return existente
            paquete_guardado = self.paquete_repo.guardar(paquete)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        # Paso 9: Intentar envío a M04 (un intento síncrono; backoff diferido fuera de alcance)
        causa_fallo = "ENVIO_INFERENCIA_NO_CONFIRMADO"
        try:
            exito = self.motor_inferencia_port.enviar_paquete(paquete_guardado)
        except MotorInferenciaNoIntegradoError:
            # Ya está confirmado en BD. No hubo transporte ni intento fallido.
            logger.warning(
                'RF-56: paquete %s pendiente; motor de inferencia no integrado.',
                paquete_guardado.id_paquetes_inferencia,
            )
            self._registrar_fallo_motor(paquete_guardado, "MOTOR_INFERENCIA_NO_INTEGRADO")
            return paquete_guardado
        except (TimeoutError, ConnectionError, ServiceUnavailableError):
            exito = False
            causa_fallo = "MOTOR_INFERENCIA_NO_DISPONIBLE"
        except Exception:
            exito = False
            causa_fallo = "ERROR_ENVIO_INFERENCIA"

        nuevo_estado = EstadoPaqueteInferencia.ENVIADO if exito else EstadoPaqueteInferencia.FALLIDO
        try:
            self.paquete_repo.actualizar_estado(
                paquete_guardado.id_paquetes_inferencia,
                nuevo_estado,
                1,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        paquete_guardado.estado_paquete = nuevo_estado
        paquete_guardado.intento_envios = 1
        if not exito:
            self._registrar_fallo_motor(paquete_guardado, causa_fallo)
        return paquete_guardado

    def _registrar_fallo_motor(self, paquete: PaqueteInferencia, causa: str) -> None:
        if self.auditoria_repo is None:
            return
        # Después del commit del paquete; nunca confirmar negocio pendiente
        # mediante el commit de la bitácora ni perderlo por un fallo del log.
        RegistrarEventoAuditoriaIotUseCase(self.db, self.auditoria_repo).execute(
            tipo_evento=causa,
            resultado=TipoResultado.ADVERTENCIA if causa == "MOTOR_INFERENCIA_NO_INTEGRADO" else TipoResultado.FALLIDO,
            componente_origen=ComponenteOrigen.RF57,
            severidad_log=SeveridadLog.WARNING,
            descripcion="Paquete sin entrega confirmada al motor de inferencia.",
            entidad_afectada_tipo=EntidadAfectadaTipo.PAQUETE_IA,
            entidad_afectada_id=str(paquete.id_paquetes_inferencia),
            accion_detallada={
                "causa": causa, "id_sensor": paquete.id_sensor,
                "id_dispositivo_iot": paquete.id_dispositivo_iot,
                "id_evento_edge_computing": paquete.id_evento_edge_computing,
                "estado_paquete": paquete.estado_paquete,
                "intento_envios": paquete.intento_envios,
            },
        )

    @staticmethod
    def _validar_timestamps(variables: list[dict]) -> None:
        """FA-03: diferencia máxima entre timestamps de variables del mismo contexto ≤ 5 s."""
        timestamps = [
            v["timestamp_captura"]
            for v in variables
            if v.get("timestamp_captura") is not None
        ]
        if len(timestamps) < 2:
            return
        ts_sorted = sorted(timestamps)
        delta = (ts_sorted[-1] - ts_sorted[0]).total_seconds() if hasattr(ts_sorted[0], 'total_seconds') else 0
        # timestamps son datetime objects
        if isinstance(ts_sorted[0], str):
            return  # no se pueden comparar strings aquí
        from datetime import datetime as dt
        if all(isinstance(t, dt) for t in ts_sorted):
            delta = (ts_sorted[-1] - ts_sorted[0]).total_seconds()
            if delta > 5:
                raise BusinessRuleError(
                    code="PAQUETE_INCONSISTENTE",
                    message="La diferencia entre timestamps de variables supera los 5 segundos permitidos.",
                )

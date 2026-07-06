from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.shared.errors import AuthenticationError, ValidationError
from src.telemetry.domain.entities.telemetria import (
    EventoEdgeComputing,
    ResultadoEventoEdge,
    TipoEventoEdge,
    clasificacion_a_tipo_evento_bd,
)
from src.telemetry.domain.repositories.dispositivo_port import DispositivoPort
from src.telemetry.domain.repositories.evento_edge_repository import EventoEdgeRepository
from src.telemetry.domain.repositories.motor_inferencia_port import MotorInferenciaPort
from src.telemetry.domain.repositories.paquete_inferencia_repository import PaqueteInferenciaRepository
from src.telemetry.infrastructure.dto.recibir_evento_edge_dto import RecibirEventoEdgeDTO
from src.telemetry.application.use_cases.inferencia.consolidar_paquete_inferencia_use_case import (
    ConsolidarEnviarPaqueteUseCase,
)

_MAX_DRIFT_FUTURO_SEG = 30
_MAX_VENTANA_BUFFER_HORAS = 72


class RecibirEventoEdgeUseCase:

    def __init__(
        self,
        db: Session,
        evento_edge_repo: EventoEdgeRepository,
        paquete_repo: PaqueteInferenciaRepository,
        dispositivo_port: DispositivoPort,
        motor_inferencia_port: MotorInferenciaPort,
    ) -> None:
        self.db = db
        self.evento_edge_repo = evento_edge_repo
        self.paquete_repo = paquete_repo
        self.dispositivo_port = dispositivo_port
        self.motor_inferencia_port = motor_inferencia_port

    def execute(
        self,
        dto: RecibirEventoEdgeDTO,
        gateway_id: Optional[str] = None,
    ) -> ResultadoEventoEdge:
        ahora = datetime.now(timezone.utc)
        ts_captura = dto.timestamp_captura
        if ts_captura.tzinfo is None:
            ts_captura = ts_captura.replace(tzinfo=timezone.utc)

        # Paso 1: Validar coherencia temporal
        self._validar_temporal(ts_captura, ahora, dto.origen)

        # Paso 2: Validar identidad del dispositivo
        dispositivo = self.dispositivo_port.obtener_dispositivo_activo(
            dto.device_id, dto.sensor_id, dto.access_key
        )
        if dispositivo is None:
            raise AuthenticationError(
                code="DISPOSITIVO_NO_AUTORIZADO",
                message="El dispositivo, sensor o credencial no son válidos o el dispositivo está inactivo.",
            )

        ts_procesamiento = dto.timestamp_procesamiento_edge
        if ts_procesamiento.tzinfo is None:
            ts_procesamiento = ts_procesamiento.replace(tzinfo=timezone.utc)

        tipo_evento_bd = clasificacion_a_tipo_evento_bd(dto.clasificacion_rf55)

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
            metadatos=dto.metadata_edge or {},
        )

        # Paso 3-4: Guardar evento
        try:
            evento_guardado = self.evento_edge_repo.guardar(evento)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        # Paso 5: Consolidar y enviar a M04 si hay desviación (fuera del bloque DB anterior)
        # ERROR_CONFIGURACION: evento guardado pero no se envía a M04 (FA-07)
        paquete_estado: Optional[str] = None
        _enviar_a_m04 = dto.clasificacion_rf55 not in (TipoEventoEdge.NORMAL, TipoEventoEdge.ERROR_CONFIGURACION)
        if _enviar_a_m04:
            consolidar = ConsolidarEnviarPaqueteUseCase(
                db=self.db,
                paquete_repo=self.paquete_repo,
                motor_inferencia_port=self.motor_inferencia_port,
            )
            paquete = consolidar.execute(evento_guardado)
            if paquete:
                paquete_estado = paquete.estado_paquete

        return ResultadoEventoEdge(
            id_evento_edge_computing=evento_guardado.id_evento_edge_computing,
            clasificacion_rf55=evento_guardado.clasificacion_rf55,
            severidad=evento_guardado.severidad,
            estado_conectividad=evento_guardado.estado_conectividad,
            fecha_procesamiento=evento_guardado.fecha_procesamiento,
            paquete_inferencia_estado=paquete_estado,
        )

    @staticmethod
    def _validar_temporal(ts_captura: datetime, ahora: datetime, origen: str) -> None:
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

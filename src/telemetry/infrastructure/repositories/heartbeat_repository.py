from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.telemetry.domain.entities.heartbeat import Heartbeat
from src.telemetry.domain.repositories.heartbeat_repository import HeartbeatRepository
from src.telemetry.infrastructure.models.heartbeat_model import HeartbeatModel


class SqlAlchemyHeartbeatRepository(HeartbeatRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def guardar(self, heartbeat: Heartbeat) -> Heartbeat:
        try:
            orm = HeartbeatModel(
                id_dispositivo_iot=heartbeat.id_dispositivo_iot,
                tipo_mensaje=heartbeat.tipo_mensaje,
                nivel_bateria_pct=heartbeat.nivel_bateria_pct,
                calidad_senal_rssi=heartbeat.calidad_senal_rssi,
                calidad_senal_snr=heartbeat.calidad_senal_snr,
                estado_local_buffer=heartbeat.estado_local_buffer,
                datos_pendientes_buffer=heartbeat.datos_pendientes_buffer,
                version_firmware=heartbeat.version_firmware,
                coordenadas=heartbeat.coordenadas,
                fecha_registro=heartbeat.fecha_registro,
                fecha_recepcion=heartbeat.fecha_recepcion,
                reloj_sincronizado=heartbeat.reloj_sincronizado,
            )
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    @staticmethod
    def _a_entidad(orm: HeartbeatModel) -> Heartbeat:
        return Heartbeat(
            id_heartbeat=orm.id_heartbeat,
            id_dispositivo_iot=orm.id_dispositivo_iot,
            tipo_mensaje=orm.tipo_mensaje,
            nivel_bateria_pct=orm.nivel_bateria_pct,
            calidad_senal_rssi=orm.calidad_senal_rssi,
            calidad_senal_snr=orm.calidad_senal_snr,
            estado_local_buffer=orm.estado_local_buffer,
            datos_pendientes_buffer=orm.datos_pendientes_buffer,
            version_firmware=orm.version_firmware,
            coordenadas=orm.coordenadas,
            fecha_registro=orm.fecha_registro,
            fecha_recepcion=orm.fecha_recepcion,
            reloj_sincronizado=orm.reloj_sincronizado,
        )

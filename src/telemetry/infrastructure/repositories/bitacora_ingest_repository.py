# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-40 RF-53: evita FK invalidas al auditar estructura |
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error

from src.telemetry.domain.repositories.bitacora_ingest_repository import BitacoraIngestRepository
from src.telemetry.infrastructure.models.bitacora_ingest_model import BitacoraIngestModel


_SEVERIDAD_POR_ESTADO: dict[str, str] = {
    'LECTURA_VALIDA': 'INFO',
    'FUERA_DE_RANGO': 'WARNING',
    'ERROR_CALIBRACION': 'WARNING',
    'ERROR_ESTRUCTURA': 'WARNING',
    'ERROR_AUTENTICACION': 'CRITICAL',
    'ERROR_DUPLICADO': 'INFO',
    'ERROR_TIEMPO': 'WARNING',
    'ERROR_UNIDAD': 'WARNING',
    'ERROR_SENSOR': 'CRITICAL',
}


class SqlAlchemyBitacoraIngestRepository(BitacoraIngestRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def registrar_exito(
        self,
        id_telemetria: int,
        id_sensor: int,
        id_dispositivo_iot: int,
        estado_calidad: str,
        timestamp_captura: datetime,
        gateway_id: Optional[str] = None,
    ) -> None:
        try:
            orm = BitacoraIngestModel(
                id_telemetria=id_telemetria,
                id_sensor=id_sensor,
                id_dispositivo_iot=id_dispositivo_iot,
                tipo_evento='DATOS_PROCESADOS',
                estado_calidad=estado_calidad,
                descripcion_text=f'Telemetría procesada con estado {estado_calidad}',
                severidad=_SEVERIDAD_POR_ESTADO.get(estado_calidad, 'INFO'),
                fecha_evento=datetime.now(timezone.utc),
                fecha_captura_dato=timestamp_captura,
                gatway_id=gateway_id,
            )
            self.db.add(orm)
            self.db.flush()
        except Exception:
            # Bitácora es best-effort — no propaga el error para no bloquear la ingesta
            pass

    def registrar_error(
        self,
        estado_calidad: str,
        descripcion: str,
        payload: Optional[dict[str, Any]],
        id_sensor: Optional[int] = None,
        id_dispositivo_iot: Optional[int] = None,
        timestamp_captura: Optional[datetime] = None,
        gateway_id: Optional[str] = None,
    ) -> None:
        try:
            if estado_calidad == 'ERROR_ESTRUCTURA' and (id_sensor is not None or id_dispositivo_iot is not None):
                # El body rechazado no garantiza referencias válidas. La sesión
                # independiente solo enlaza filas que realmente puede consultar;
                # los IDs recibidos permanecen en el contexto técnico saneado.
                referencias = self.db.execute(text('''
                    SELECT
                      (SELECT id_sensores FROM modulo9.sensores WHERE id_sensores=:sensor) AS sensor,
                      (SELECT id_dispositivo_iot FROM modulo9.dispositivos_iot WHERE id_dispositivo_iot=:dispositivo) AS dispositivo
                '''), {'sensor': id_sensor, 'dispositivo': id_dispositivo_iot}).mappings().one()
                id_sensor = referencias['sensor']
                id_dispositivo_iot = referencias['dispositivo']
            orm = BitacoraIngestModel(
                id_telemetria=None,
                id_sensor=id_sensor,
                id_dispositivo_iot=id_dispositivo_iot,
                tipo_evento='ERROR_PROCESAMIENTO',
                estado_calidad=estado_calidad,
                descripcion_text=descripcion,
                payload_recibido=payload,
                severidad=_SEVERIDAD_POR_ESTADO.get(estado_calidad, 'WARNING'),
                fecha_evento=datetime.now(timezone.utc),
                fecha_captura_dato=timestamp_captura,
                gatway_id=gateway_id,
            )
            self.db.add(orm)
            self.db.flush()
        except Exception as exc:
            # El caso de uso revierte esta transacción de auditoría sin
            # sustituir el rechazo funcional original.
            raise_from_db_error(exc)

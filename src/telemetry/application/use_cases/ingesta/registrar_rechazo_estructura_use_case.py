# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-40 RF-53: persiste rechazos estructurales      |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Bitácora de rechazos anteriores al caso de uso de ingesta."""
import logging

from src.telemetry.domain.repositories.bitacora_ingest_repository import BitacoraIngestRepository

logger = logging.getLogger(__name__)


class RegistrarRechazoEstructuraUseCase:
    """Recibe una sesión exclusiva: nunca confirma la transacción de ingesta."""

    def __init__(self, db, bitacora_repo: BitacoraIngestRepository) -> None:
        self.db = db
        self.bitacora_repo = bitacora_repo

    def execute(self, contexto: dict) -> None:
        """Registra en la bitácora de ingesta una solicitud rechazada por estructura."""
        try:
            self.bitacora_repo.registrar_error(
                estado_calidad='ERROR_ESTRUCTURA',
                descripcion='RF-53: solicitud rechazada por estructura antes de la ingesta.',
                payload=contexto,
                id_sensor=contexto.get('sensor_id'),
                id_dispositivo_iot=contexto.get('device_id'),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            # Misma política best-effort de auditoría del proyecto. No exponer
            # la excepción ni sustituir la respuesta de validación original.
            logger.warning('RF-53: no se pudo persistir ERROR_ESTRUCTURA en bitacora_ingest.')

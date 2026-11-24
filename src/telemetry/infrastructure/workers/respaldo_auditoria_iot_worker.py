# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-26 | Leandro | INC-M03-125-G12 RF-53/63: sincronizar evidencia pendiente tras recuperar PostgreSQL y esperar el cierre de cada transacción. |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo y funciones |
"""Worker periódico que sincroniza el respaldo de auditoría IoT (RF-53/RF-63).

Cuando PostgreSQL no está disponible, la evidencia se guarda en SQLite. Este
worker reintenta su sincronización cada ``IOT_AUDITORIA_RESPALDO_INTERVALO_SEG``
segundos y conserva el respaldo si el intento falla.
"""
import asyncio
import logging
import os
from src.shared.database import sesion_sistema
from src.telemetry.infrastructure.adapters.respaldo_auditoria_iot_sqlite_adapter import RespaldoAuditoriaIotSqliteAdapter
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import SqlAlchemyBitacoraAuditoriaIotRepository
from src.telemetry.application.use_cases.auditoria.sincronizar_respaldo_auditoria_iot_use_case import SincronizarRespaldoAuditoriaIotUseCase

logger = logging.getLogger(__name__)


def sincronizar_respaldo():
    """Sincroniza una vez la evidencia pendiente y devuelve cuántos eventos procesó.

    No abre sesión si no hay pendientes.
    """
    respaldo = RespaldoAuditoriaIotSqliteAdapter()
    if not respaldo.hay_pendientes():
        return 0
    with sesion_sistema() as db:
        return SincronizarRespaldoAuditoriaIotUseCase(db, SqlAlchemyBitacoraAuditoriaIotRepository(db), respaldo).execute()


async def sincronizar_respaldo_auditoria_iot_periodicamente():
    """Ejecuta la sincronización del respaldo en un bucle hasta que se cancele.

    Espera a que termine cada intento (incluso si la tarea se cancela) para no
    dejar transacciones a medias, y conserva el respaldo ante cualquier fallo.
    """
    intervalo = max(1, int(os.getenv('IOT_AUDITORIA_RESPALDO_INTERVALO_SEG', '5')))
    while True:
        trabajo = asyncio.create_task(asyncio.to_thread(sincronizar_respaldo))
        try:
            await asyncio.shield(trabajo)
        except asyncio.CancelledError:
            try:
                await trabajo
            except Exception:
                logger.error('RF-63: la recuperación interrumpida conserva su respaldo pendiente.')
            raise
        except Exception:
            logger.error('RF-63: no se completó la recuperación de evidencia de ingesta; el respaldo se conserva.')
        await asyncio.sleep(intervalo)

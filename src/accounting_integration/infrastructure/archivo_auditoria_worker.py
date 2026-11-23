# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-19 | Leandro | INC-M07-371-G58 RF-102: programar archivado, reintentos y alerta crítica. |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Tarea de fondo de RF-102. Los lotes confirmados se conservan si falla otro lote."""
import asyncio
import logging

from src.accounting_integration.application.use_cases.auditoria.archivar_auditoria_integracion_use_case import (
    ArchivarAuditoriaIntegracionUseCase,
)
from src.accounting_integration.infrastructure.adapters.alerta_administrador_adapter import alertador_administrador
from src.accounting_integration.infrastructure.repositories.auditoria_integracion_repository import (
    SqlAlchemyAuditoriaIntegracionRepository,
)
from src.shared.database import sesion_sistema

logger = logging.getLogger(__name__)
_INTERVALO = 60 * 60
_REINTENTO = 15 * 60


def ejecutar_archivado() -> bool:
    """Archiva todos los lotes vencidos; ``True`` si terminó sin errores."""
    alertar = alertador_administrador(sesion_sistema)
    total = 0
    cursor = None
    try:
        with sesion_sistema() as db:
            caso = ArchivarAuditoriaIntegracionUseCase(SqlAlchemyAuditoriaIntegracionRepository(db), db)
            while True:
                cursor, archivados, corruptos = caso.ejecutar_lote(cursor)
                total += archivados
                if corruptos:
                    logger.critical("RF-102: %d eventos con hash inválido permanecen en la bitácora activa.", len(corruptos))
                    alertar("El archivado de auditoría encontró registros con integridad inválida.",
                            {"causa": "HASH_INVALIDO_ARCHIVADO", "ids_evento": corruptos})
                if cursor is None:
                    break
    except Exception as exc:
        logger.critical("RF-102: archivado interrumpido tras confirmar %d eventos (%s).", total, type(exc).__name__)
        alertar("Falló el archivado de la auditoría de integración. El sistema volverá a intentarlo.",
                {"causa": "FALLO_ARCHIVADO", "error": type(exc).__name__})
        return False
    if total:
        logger.info("RF-102: %d registros de auditoría archivados.", total)
    return True


async def archivar_auditoria_integracion_periodicamente() -> None:
    """Ejecuta el archivado de auditoría de integración en bucle."""
    while True:
        tarea = asyncio.create_task(asyncio.to_thread(ejecutar_archivado))
        try:
            completo = await asyncio.shield(tarea)
        except asyncio.CancelledError:
            await tarea
            raise
        await asyncio.sleep(_INTERVALO if completo else _REINTENTO)

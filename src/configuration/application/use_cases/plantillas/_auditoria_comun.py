"""Auditoría de intentos fallidos, compartida entre los use cases de plantillas.

INC-M09-01-109 (#319): el RF-30 exige que los intentos fallidos de cualquier
operación sobre plantillas queden auditados. Un `INSERT` hecho con `flush()`
dentro de la misma transacción que falló se pierde en el `rollback()` de esa
transacción — por eso este registro va en una transacción propia, después de
deshacer la operación principal.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from src.configuration.domain.repositories.auditoria_plantilla_repository import AuditoriaPlantillaRepository

logger = logging.getLogger(__name__)


def registrar_intento_fallido(
    db: Session,
    auditoria_repo: AuditoriaPlantillaRepository,
    *,
    id_usuario: int,
    tipo_operacion: str,
    detalle: dict[str, Any],
    id_plantilla: Optional[int] = None,
) -> None:
    """Deshace la operación principal y audita el fallo en una transacción propia.

    Best-effort: si el propio registro de auditoría falla, no vuelve a lanzar —
    un error de infraestructura en la auditoría no debe ocultar el error de
    negocio original que ya se está propagando.
    """
    db.rollback()
    try:
        auditoria_repo.registrar(
            id_plantilla=id_plantilla,
            id_usuario=id_usuario,
            tipo_operacion=tipo_operacion,
            resultado="FALLIDO",
            valores_nuevos=detalle,
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "No se pudo registrar el intento fallido de %s sobre la plantilla %s.",
            tipo_operacion,
            id_plantilla,
        )

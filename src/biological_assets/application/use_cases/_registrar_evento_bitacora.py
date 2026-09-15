"""RF-52 restricción 3: un fallo en la bitácora no bloquea el flujo operativo
de M02. Pero el patrón anterior (`except Exception: pass`) descartaba ese
fallo sin dejar rastro — la ausencia de un evento dejaba de probar que la
operación no ocurrió (issue #265). `registrar_evento_bitacora` conserva el
"mejor esfuerzo" (la operación de negocio ya se resolvió, nunca se revierte
por esto) pero deja constancia siempre: log de aplicación con severidad
ERROR y, para poder contarlos sin repasar logs a mano, una línea en un
archivo de fallback local — mismo mecanismo que ya usa
`src/prediction/infrastructure/repositories/evento_auditoria_m04_repository.py`
para el mismo problema en M04.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import EventoAuditoria
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import (
    BitacoraAuditoriaRepository,
)

logger = logging.getLogger(__name__)


def _escribir_fallback(evento: EventoAuditoria, error: Exception) -> None:
    try:
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        archivo = logs_dir / f"audit_fallback_M02_{datetime.now(timezone.utc):%Y%m%d}.log"
        linea = json.dumps(
            {
                "rf_origen": evento.rf_origen,
                "tipo_evento": evento.tipo_evento,
                "clasificacion_biologica": evento.clasificacion_biologica,
                "resultado": evento.resultado,
                "id_activo_biologico": evento.id_activo_biologico,
                "id_usuario_responsable": evento.id_usuario_responsable,
                "timestamp_evento": evento.timestamp_evento.isoformat(),
                "error": str(error),
            },
            default=str,
        )
        with open(archivo, "a", encoding="utf-8") as f:
            f.write(linea + "\n")
    except Exception:
        logger.exception("No se pudo escribir el fallback de auditoría RF-52 (M02)")


def registrar_evento_bitacora(
    bitacora_repo: BitacoraAuditoriaRepository | None,
    db: Session,
    evento: EventoAuditoria,
) -> None:
    """Registra `evento` en RF-52 sin bloquear ni revertir la operación de negocio.

    Si `bitacora_repo` es None, no hace nada (auditoría no configurada). Si el
    registro falla, se revierte solo el intento de escritura de auditoría
    (`db.rollback()`), se deja evidencia en el log de aplicación con
    severidad ERROR y en el archivo de fallback — nunca se propaga la
    excepción, para no tumbar un flujo operativo válido de M02 por un
    problema de infraestructura de auditoría.
    """
    if bitacora_repo is None:
        return
    try:
        bitacora_repo.registrar(evento)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(
            "Fallo al registrar evento de auditoría RF-52: rf_origen=%s tipo_evento=%s "
            "id_activo=%s id_usuario=%s",
            evento.rf_origen,
            evento.tipo_evento,
            evento.id_activo_biologico,
            evento.id_usuario_responsable,
            exc_info=True,
        )
        _escribir_fallback(evento, exc)

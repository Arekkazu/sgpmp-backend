"""RF-52 restricción 3: un fallo en la bitácora no bloquea el flujo operativo
de M02. Pero el patrón anterior (`except Exception: pass`) descartaba ese
fallo sin dejar rastro — la ausencia de un evento dejaba de probar que la
operación no ocurrió (issue #265). `registrar_evento_bitacora` conserva el
"mejor esfuerzo" (la operación de negocio ya se resolvió, nunca se revierte
por esto) pero deja constancia siempre: log de aplicación con severidad
ERROR y el evento completo en un buffer local.

RF-52 E1 ("Fallo persistente del repositorio de auditoría"): ese buffer no es
solo evidencia, se recupera. La primera escritura exitosa después del fallo
persiste los eventos pendientes en orden cronológico y deja un registro
INDISPONIBILIDAD_AUDITORIA con el periodo que la bitácora estuvo caída.
"""
from __future__ import annotations

import fcntl
import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import EventoAuditoria
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import (
    BitacoraAuditoriaRepository,
)

logger = logging.getLogger(__name__)

# Relativos al directorio de trabajo, como el resto de logs/ del backend.
_BUFFER = Path("logs") / "audit_buffer_M02.jsonl"
_LOCK = Path("logs") / "audit_buffer_M02.lock"


@contextmanager
def _bloqueo(esperar: bool = True) -> Iterator[None]:
    """Exclusión entre procesos (workers de uvicorn) sobre el buffer.

    Con ``esperar=False`` lanza ``BlockingIOError`` si otro proceso ya lo tiene.
    """
    _LOCK.parent.mkdir(exist_ok=True)
    with open(_LOCK, "a") as candado:
        fcntl.flock(candado, fcntl.LOCK_EX if esperar else fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(candado, fcntl.LOCK_UN)


def _guardar_en_buffer(evento: EventoAuditoria, error: Exception) -> None:
    try:
        linea = json.dumps(
            {
                "evento": asdict(evento),
                "fallo_en": datetime.now(timezone.utc).isoformat(),
                "error": str(error),
            },
            default=str,
        )
        with _bloqueo():
            with open(_BUFFER, "a", encoding="utf-8") as f:
                f.write(linea + "\n")
    except Exception:
        logger.exception("No se pudo guardar el evento en el buffer de auditoría RF-52 (M02)")


def _evento_desde_buffer(datos: dict) -> EventoAuditoria:
    datos["timestamp_evento"] = datetime.fromisoformat(datos["timestamp_evento"])
    return EventoAuditoria(**datos)


def _recuperar_buffer(bitacora_repo: BitacoraAuditoriaRepository, db: Session) -> None:
    if not _BUFFER.exists():
        return
    try:
        with _bloqueo(esperar=False):
            pendientes = []
            for linea in _BUFFER.read_text(encoding="utf-8").splitlines():
                if not linea.strip():
                    continue
                try:
                    pendientes.append(json.loads(linea))
                except json.JSONDecodeError:
                    # Línea truncada por un proceso que murió a mitad de escritura:
                    # no es recuperable, pero no puede bloquear al resto del buffer.
                    logger.error("Línea ilegible en el buffer de auditoría RF-52, se descarta: %r", linea)

            eventos = sorted(
                (_evento_desde_buffer(p["evento"]) for p in pendientes),
                key=lambda e: e.timestamp_evento,
            )
            for evento in eventos:
                bitacora_repo.registrar(evento)
            if pendientes:
                recuperado_en = datetime.now(timezone.utc)
                bitacora_repo.registrar(EventoAuditoria(
                    rf_origen="RF52",
                    tipo_evento="INDISPONIBILIDAD_AUDITORIA",
                    clasificacion_biologica="GESTION_OPERATIVA",
                    resultado="EXITOSO",
                    severidad_log="WARNING",
                    timestamp_evento=recuperado_en,
                    descripcion=f"Bitácora recuperada: {len(eventos)} eventos persistidos desde el buffer.",
                    detalle_tecnico={
                        "desde": min(p["fallo_en"] for p in pendientes),
                        "hasta": recuperado_en.isoformat(),
                        "eventos_recuperados": len(eventos),
                    },
                ))
            db.commit()
            _BUFFER.unlink()
    except BlockingIOError:
        return  # otro proceso está escribiendo o recuperando el buffer
    except Exception:
        db.rollback()
        logger.exception("No se pudo recuperar el buffer de auditoría RF-52 (M02); se reintentará")


def registrar_evento_bitacora(
    bitacora_repo: BitacoraAuditoriaRepository | None,
    db: Session,
    evento: EventoAuditoria,
) -> None:
    """Registra `evento` en RF-52 sin bloquear ni revertir la operación de negocio.

    Si `bitacora_repo` es None, no hace nada (auditoría no configurada). Si el
    registro falla, se revierte solo el intento de escritura de auditoría
    (`db.rollback()`), se alerta con severidad CRITICAL en el log de aplicación
    y el evento queda en el buffer local — nunca se propaga la excepción, para
    no tumbar un flujo operativo válido de M02 por un problema de
    infraestructura de auditoría. Si la escritura funciona, se aprovecha para
    vaciar lo que haya quedado en el buffer.
    """
    if bitacora_repo is None:
        return
    try:
        bitacora_repo.registrar(evento)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.critical(
            "Fallo al registrar evento de auditoría RF-52: rf_origen=%s tipo_evento=%s "
            "id_activo=%s id_usuario=%s. El evento queda en %s hasta que la bitácora se recupere.",
            evento.rf_origen,
            evento.tipo_evento,
            evento.id_activo_biologico,
            evento.id_usuario_responsable,
            _BUFFER,
            exc_info=True,
        )
        _guardar_en_buffer(evento, exc)
        return

    _recuperar_buffer(bitacora_repo, db)

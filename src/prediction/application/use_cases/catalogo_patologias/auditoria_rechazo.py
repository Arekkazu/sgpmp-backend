# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-03 | Arekkazu | QA-M04 ronda 2 CU01 H-11 RF-64/RF-73: los intentos rechazados sobre el catálogo quedan en la bitácora |
"""RF-64 paso 6 / CU-01 paso 16: toda operación sobre el catálogo se audita, también la rechazada."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.shared.errors import AppError


def auditar_rechazo(
    db: Session,
    auditoria_repo: EventoAuditoriaM04Repository,
    *,
    tipo_evento: str,
    id_usuario: int,
    referencia: str,
    payload: dict,
    error: AppError,
) -> None:
    """Registra el intento como FALLIDO con el motivo; nunca tapa el error original."""
    db.rollback()
    try:
        auditoria_repo.registrar(
            tipo_evento=tipo_evento,
            tipo_actor="USUARIO",
            id_usuario=id_usuario,
            id_referencia=referencia,
            entidad_referencia="patologia" if referencia.isdigit() else None,
            resultado_operacion="FALLIDO",
            severidad_evento="WARNING",
            codigo_error=error.code[:50],
            descripcion_error=error.message,
            payload_evento={**payload, "motivo_rechazo": error.code},
        )
        db.commit()
    except Exception:
        db.rollback()


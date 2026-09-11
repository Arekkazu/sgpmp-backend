"""Implementación SQLAlchemy del puerto ``AuditoriaIdentidadVisualRepository`` (RF-26)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.configuration.domain.repositories.auditoria_identidad_visual_repository import AuditoriaIdentidadVisualRepository
from src.configuration.infrastructure.models.auditoria_identidad_visual_model import AuditoriaIdentidadVisualModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyAuditoriaIdentidadVisualRepository(AuditoriaIdentidadVisualRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def registrar(
        self,
        *,
        id_usuario: int,
        valor_anterior: dict,
        valor_nuevo: dict,
    ) -> None:
        orm = AuditoriaIdentidadVisualModel(
            id_usuario=id_usuario,
            fecha_creacion=datetime.now(timezone.utc),
            valor_anterior=valor_anterior,
            valor_nuevo=valor_nuevo,
        )
        try:
            self.db.add(orm)
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc)

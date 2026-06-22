"""Implementación SQLAlchemy de ``AuditoriaInfraestructuraRepository``."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from src.configuration.domain.repositories.auditoria_infraestructura_repository import AuditoriaInfraestructuraRepository
from src.configuration.infrastructure.models.auditoria_infraestructura_model import AuditoriaInfraestructuraModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyAuditoriaInfraestructuraRepository(AuditoriaInfraestructuraRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def registrar(
        self,
        *,
        id_infraestructura: int,
        id_usuario: int,
        tipo_operacion: str,
        valores_nuevos: dict[str, Any],
        valores_anteriores: Optional[dict[str, Any]] = None,
    ) -> None:
        orm = AuditoriaInfraestructuraModel(
            id_infraestructura=id_infraestructura,
            id_usuario=id_usuario,
            tipo_operacion=tipo_operacion,
            valores_nuevos=valores_nuevos,
            valores_anteriores=valores_anteriores,
        )
        try:
            self.db.add(orm)
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc)

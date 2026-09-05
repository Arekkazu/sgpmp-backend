"""Implementación SQLAlchemy del puerto :class:`AuditoriaCicloRepository`."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from src.configuration.domain.repositories.auditoria_ciclo_repository import AuditoriaCicloRepository
from src.configuration.infrastructure.models.auditoria_ciclo_biologico_model import AuditoriaCicloBiologicoModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyAuditoriaCicloRepository(AuditoriaCicloRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def registrar(
        self,
        *,
        id_ciclo_biologico: int,
        id_usuario: int,
        tipo_operacion: str,
        valores_nuevos: dict[str, Any],
        valores_anteriores: Optional[dict[str, Any]] = None,
    ) -> None:
        orm = AuditoriaCicloBiologicoModel(
            id_ciclo_biologico=id_ciclo_biologico,
            id_usuario=id_usuario,
            tipo_operacion=tipo_operacion,
            valores_nuevos=valores_nuevos,
            valores_anteriores=valores_anteriores,
        )
        try:
            self.db.add(orm)
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc, {})

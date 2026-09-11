"""Implementación SQLAlchemy del puerto :class:`AuditoriaEspecieRepository`.

Registro append-only: solo inserta, nunca actualiza ni elimina.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from src.configuration.domain.repositories.auditoria_especie_repository import AuditoriaEspecieRepository
from src.configuration.infrastructure.models.auditoria_especie_model import AuditoriaEspecieModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyAuditoriaEspecieRepository(AuditoriaEspecieRepository):
    """Adaptador SQLAlchemy para ``modulo9.auditorias_especies``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def registrar(
        self,
        *,
        id_especie: int,
        id_usuario: int,
        tipo_operacion: str,
        valores_nuevos: dict[str, Any],
        valores_anteriores: Optional[dict[str, Any]] = None,
    ) -> None:
        orm = AuditoriaEspecieModel(
            id_especie=id_especie,
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

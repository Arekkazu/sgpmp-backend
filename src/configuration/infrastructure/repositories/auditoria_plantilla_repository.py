"""Implementación SQLAlchemy del puerto :class:`AuditoriaPlantillaRepository`.

Registro append-only: solo inserta, nunca actualiza ni elimina.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from src.configuration.domain.repositories.auditoria_plantilla_repository import AuditoriaPlantillaRepository
from src.configuration.infrastructure.models.auditoria_plantilla_model import AuditoriaPlantillaModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyAuditoriaPlantillaRepository(AuditoriaPlantillaRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def registrar(
        self,
        *,
        id_plantilla: int,
        id_usuario: int,
        tipo_operacion: str,
        valores_nuevos: dict[str, Any],
        valores_anteriores: Optional[dict[str, Any]] = None,
    ) -> None:
        orm = AuditoriaPlantillaModel(
            id_plantilla=id_plantilla,
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

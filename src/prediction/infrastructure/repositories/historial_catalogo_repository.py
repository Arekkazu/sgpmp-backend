# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Implementación SQLAlchemy de ``HistorialCatalogoRepository``."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.prediction.domain.repositories.historial_catalogo_repository import HistorialCatalogoRepository
from src.prediction.infrastructure.models.historial_catalogo_model import HistorialCatalogoModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyHistorialCatalogoRepository(HistorialCatalogoRepository):
    """Implementación SQLAlchemy de ``HistorialCatalogoRepository``."""
    def __init__(self, db: Session) -> None:
        self._db = db

    def registrar(
        self,
        *,
        id_patologia: int,
        version_catalogo: int,
        accion: str,
        datos_nuevos: dict,
        id_usuario: int,
        datos_anteriores: Optional[dict] = None,
    ) -> None:
        """Registra una versión del catálogo."""
        try:
            self._db.add(
                HistorialCatalogoModel(
                    id_patologia=id_patologia,
                    version_catalogo=version_catalogo,
                    accion=accion,
                    datos_nuevos=datos_nuevos,
                    datos_anteriores=datos_anteriores,
                    id_usuario=id_usuario,
                )
            )
            self._db.flush()
        except Exception as exc:
            raise_from_db_error(exc)

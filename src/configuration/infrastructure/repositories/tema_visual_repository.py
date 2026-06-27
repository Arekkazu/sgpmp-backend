"""Implementación SQLAlchemy del puerto ``TemaVisualRepository`` (RF-27)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.entities.tema_visual import TemaVisual, ThemeMode
from src.configuration.domain.repositories.tema_visual_repository import TemaVisualRepository
from src.configuration.infrastructure.models.tema_visual_model import TemaVisualModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyTemaVisualRepository(TemaVisualRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: TemaVisualModel) -> TemaVisual:
        return TemaVisual(
            id_tema_visual=orm.id_tema_visual,
            id_usuario=orm.id_usuario,
            theme_mode=ThemeMode(orm.theme_mode),
            es_global=orm.es_global,
            fecha_actualizacion=orm.fecha_actualizacion,
        )

    def obtener_por_usuario(self, id_usuario: int) -> Optional[TemaVisual]:
        orm = (
            self.db.query(TemaVisualModel)
            .filter(
                TemaVisualModel.id_usuario == id_usuario,
                TemaVisualModel.es_global.is_(False),
            )
            .order_by(
                TemaVisualModel.fecha_actualizacion.desc(),
                TemaVisualModel.id_tema_visual.desc(),
            )
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def obtener_global(self) -> Optional[TemaVisual]:
        orm = (
            self.db.query(TemaVisualModel)
            .filter(TemaVisualModel.es_global.is_(True))
            .order_by(
                TemaVisualModel.fecha_actualizacion.desc(),
                TemaVisualModel.id_tema_visual.desc(),
            )
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def guardar(self, entidad: TemaVisual) -> TemaVisual:
        orm = TemaVisualModel(
            id_usuario=entidad.id_usuario,
            theme_mode=entidad.theme_mode.value,
            es_global=entidad.es_global,
            fecha_actualizacion=entidad.fecha_actualizacion,
        )
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc)
        return self._a_entidad(orm)

    def actualizar(self, entidad: TemaVisual) -> TemaVisual:
        orm = self.db.get(TemaVisualModel, entidad.id_tema_visual)
        orm.theme_mode = entidad.theme_mode.value
        orm.fecha_actualizacion = entidad.fecha_actualizacion
        try:
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc)
        return self._a_entidad(orm)

"""Implementación SQLAlchemy del puerto :class:`PatologiaRepository`.

Solo toca nombre, descripcion, es_activo y fecha_actualizacion.
Los campos de M04 se preservan sin modificar.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.configuration.domain.entities.patologia import Patologia
from src.configuration.domain.repositories.patologia_repository import PatologiaRepository
from src.configuration.domain.value_objects.nombre_patologia import NombrePatologia
from src.configuration.infrastructure.models.patologia_model import PatologiaModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyPatologiaRepository(PatologiaRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: PatologiaModel) -> Patologia:
        return Patologia(
            id_patologia=orm.id_patologia,
            nombre=NombrePatologia(orm.nombre),
            descripcion=orm.descripcion,
            es_activo=orm.es_activo,
            fecha_actualizacion=orm.fecha_actualizacion,
        )

    def obtener_por_id(self, id_patologia: int) -> Optional[Patologia]:
        orm = self.db.get(PatologiaModel, id_patologia)
        return self._a_entidad(orm) if orm else None

    def obtener_por_nombre(self, nombre: NombrePatologia) -> Optional[Patologia]:
        orm = (
            self.db.query(PatologiaModel)
            .filter(func.lower(PatologiaModel.nombre) == nombre.normalizado())
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def guardar(self, patologia: Patologia, id_usuario_creador: Optional[int] = None) -> Patologia:
        orm = PatologiaModel(
            nombre=patologia.nombre.valor,
            descripcion=patologia.descripcion,
            es_activo=patologia.es_activo,
            id_usuario_creador=id_usuario_creador,
        )
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {
                "uq_enfermedad_nombre": (
                    f"La patología '{patologia.nombre.valor}' ya existe en el catálogo."
                ),
            })
        return self._a_entidad(orm)

    def actualizar(self, patologia: Patologia) -> Patologia:
        orm = self.db.get(PatologiaModel, patologia.id_patologia)
        orm.nombre = patologia.nombre.valor
        orm.descripcion = patologia.descripcion
        orm.es_activo = patologia.es_activo
        orm.fecha_actualizacion = patologia.fecha_actualizacion
        try:
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {
                "uq_enfermedad_nombre": (
                    f"El nombre '{patologia.nombre.valor}' ya existe en el catálogo de patologías."
                ),
            })
        return self._a_entidad(orm)

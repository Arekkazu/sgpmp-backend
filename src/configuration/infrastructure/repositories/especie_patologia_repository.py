"""Implementación SQLAlchemy del puerto :class:`EspeciePatologiaRepository`.

Gestiona la tabla ``modulo9.especies_patologias`` como entidad M09 de patologías
por especie. No toca el catálogo clínico M04 (``modulo9.patologias``).
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.configuration.domain.entities.especie_patologia import EspeciePatologia
from src.configuration.domain.repositories.especie_patologia_repository import EspeciePatologiaRepository
from src.configuration.domain.value_objects.nombre_patologia import NombrePatologia
from src.configuration.infrastructure.models.especie_patologia_model import EspeciePatologiaModel
from src.shared.db_error_translator import raise_from_db_error

_DUP_MSG = "Ya existe una patología con ese nombre para esta especie."


class SqlAlchemyEspeciePatologiaRepository(EspeciePatologiaRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: EspeciePatologiaModel) -> EspeciePatologia:
        return EspeciePatologia(
            id_especies_patologias=orm.id_especies_patologias,
            id_especie=orm.id_especie,
            id_patologia=orm.id_patologia,
            nombre=NombrePatologia(orm.nombre),
            descripcion=orm.descripcion,
            es_activo=orm.es_activo,
            fecha_actualizacion=orm.fecha_actualizacion,
            fecha_creacion=orm.fecha_creacion,
        )

    def obtener_por_id(self, id_especies_patologias: int) -> Optional[EspeciePatologia]:
        orm = self.db.get(EspeciePatologiaModel, id_especies_patologias)
        return self._a_entidad(orm) if orm else None

    def obtener_por_especie_y_nombre(
        self, id_especie: int, nombre: NombrePatologia
    ) -> Optional[EspeciePatologia]:
        orm = (
            self.db.query(EspeciePatologiaModel)
            .filter(
                EspeciePatologiaModel.id_especie == id_especie,
                func.lower(EspeciePatologiaModel.nombre) == nombre.normalizado(),
            )
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def listar_por_especie(
        self, id_especie: int, *, solo_activas: bool = False
    ) -> list[EspeciePatologia]:
        query = self.db.query(EspeciePatologiaModel).filter(
            EspeciePatologiaModel.id_especie == id_especie,
        )
        if solo_activas:
            query = query.filter(EspeciePatologiaModel.es_activo.is_(True))
        return [
            self._a_entidad(orm)
            for orm in query.order_by(EspeciePatologiaModel.nombre).all()
        ]

    def guardar(self, entidad: EspeciePatologia) -> EspeciePatologia:
        orm = EspeciePatologiaModel(
            id_especie=entidad.id_especie,
            id_patologia=entidad.id_patologia,
            nombre=entidad.nombre.valor,
            descripcion=entidad.descripcion,
            es_activo=entidad.es_activo,
        )
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {"uq_especie_patologia_nombre": _DUP_MSG})
        return self._a_entidad(orm)

    def actualizar(self, entidad: EspeciePatologia) -> EspeciePatologia:
        orm = self.db.get(EspeciePatologiaModel, entidad.id_especies_patologias)
        orm.nombre = entidad.nombre.valor
        orm.descripcion = entidad.descripcion
        orm.es_activo = entidad.es_activo
        orm.fecha_actualizacion = entidad.fecha_actualizacion
        try:
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {"uq_especie_patologia_nombre": _DUP_MSG})
        return self._a_entidad(orm)

    def eliminar_todas_de_especie(self, id_especie: int) -> None:
        try:
            self.db.query(EspeciePatologiaModel).filter(
                EspeciePatologiaModel.id_especie == id_especie,
            ).delete(synchronize_session='fetch')
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc, {})

    def vincular_desde_snapshot(self, id_especie: int, datos: dict) -> None:
        orm = EspeciePatologiaModel(
            id_especie=id_especie,
            nombre=datos["nombre"],
            descripcion=datos.get("descripcion"),
            es_activo=datos.get("es_activo", True),
        )
        try:
            self.db.add(orm)
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc, {"uq_especie_patologia_nombre": _DUP_MSG})

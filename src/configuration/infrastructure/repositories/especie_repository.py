"""Implementación SQLAlchemy del puerto :class:`EspecieRepository`.

Único punto donde se cruza la frontera ORM ↔ dominio para el agregado
``Especie``: traduce ``EspecieModel`` → ``Especie`` al leer y
``Especie`` → ``EspecieModel`` al escribir. El resto de la aplicación
trabaja siempre con la entidad pura.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.configuration.domain.entities.especie import Especie
from src.configuration.domain.repositories.especie_repository import EspecieRepository
from src.configuration.domain.value_objects.nombre_especie import NombreEspecie
from src.configuration.infrastructure.models.especie_model import EspecieModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyEspecieRepository(EspecieRepository):
    """Adaptador SQLAlchemy que mapea entre ``modulo9.especies`` y la entidad."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Mapeo ORM ↔ dominio ─────────────────────────────────────────────────

    @staticmethod
    def _a_entidad(orm: EspecieModel) -> Especie:
        return Especie(
            id_especie=orm.id_especie,
            nombre=NombreEspecie(orm.nombre),
            descripcion=orm.descripcion,
            es_activo=orm.es_activo,
            fecha_creacion=orm.fecha_creacion,
            fecha_actualizacion=orm.fecha_actualizacion,
        )

    @staticmethod
    def _a_orm(especie: Especie) -> EspecieModel:
        return EspecieModel(
            nombre=especie.nombre.valor,
            descripcion=especie.descripcion,
            es_activo=especie.es_activo,
            fecha_creacion=especie.fecha_creacion or datetime.now(timezone.utc),
        )

    # ── Operaciones del puerto ───────────────────────────────────────────────

    def obtener_por_id(self, id_especie: int) -> Optional[Especie]:
        orm = self.db.get(EspecieModel, id_especie)
        return self._a_entidad(orm) if orm else None

    def obtener_por_nombre(self, nombre: NombreEspecie) -> Optional[Especie]:
        orm = (
            self.db.query(EspecieModel)
            .filter(func.lower(EspecieModel.nombre) == nombre.normalizado())
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def guardar(self, especie: Especie) -> Especie:
        orm = self._a_orm(especie)
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {
                "uq_especie_nombre": (
                    f"La especie '{especie.nombre.valor}' ya se encuentra registrada en el catálogo."
                ),
            })
        return self._a_entidad(orm)

    def actualizar(self, especie: Especie) -> Especie:
        orm = self.db.get(EspecieModel, especie.id_especie)
        orm.nombre = especie.nombre.valor
        orm.descripcion = especie.descripcion
        orm.es_activo = especie.es_activo
        orm.fecha_actualizacion = especie.fecha_actualizacion
        try:
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {
                "uq_especie_nombre": (
                    f"El nombre '{especie.nombre.valor}' ya pertenece a otra especie del catálogo."
                ),
            })
        return self._a_entidad(orm)

    def listar(self, *, solo_activas: bool = False) -> list[Especie]:
        query = self.db.query(EspecieModel)
        if solo_activas:
            query = query.filter(EspecieModel.es_activo.is_(True))
        return [
            self._a_entidad(orm)
            for orm in query.order_by(EspecieModel.nombre).all()
        ]

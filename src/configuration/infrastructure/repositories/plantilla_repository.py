"""Implementación SQLAlchemy del puerto :class:`PlantillaRepository`."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.configuration.domain.entities.plantilla import Plantilla
from src.configuration.domain.repositories.plantilla_repository import PlantillaRepository
from src.configuration.infrastructure.models.plantilla_model import PlantillaModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyPlantillaRepository(PlantillaRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: PlantillaModel) -> Plantilla:
        return Plantilla(
            id_plantilla=orm.id_plantilla,
            id_especie=orm.id_especie,
            id_usuario=orm.id_usuario,
            template_name=orm.template_name,
            params_snapshot=orm.params_snapshot,
            version=orm.version,
            fecha_creacion=orm.fecha_creacion,
        )

    def obtener_por_id(self, id_plantilla: int) -> Optional[Plantilla]:
        orm = self.db.get(PlantillaModel, id_plantilla)
        return self._a_entidad(orm) if orm else None

    def existe_nombre(self, template_name: str) -> bool:
        return self.db.scalar(
            select(func.count(PlantillaModel.id_plantilla)).where(
                func.lower(func.trim(PlantillaModel.template_name))
                == func.lower(func.trim(template_name))
            )
        ) > 0

    def listar_todas(self) -> list[Plantilla]:
        rows = (
            self.db.query(PlantillaModel)
            .order_by(PlantillaModel.template_name, PlantillaModel.version.desc())
            .all()
        )
        return [self._a_entidad(r) for r in rows]

    def guardar(self, plantilla: Plantilla) -> Plantilla:
        orm = PlantillaModel(
            id_especie=plantilla.id_especie,
            id_usuario=plantilla.id_usuario,
            template_name=plantilla.template_name,
            params_snapshot=plantilla.params_snapshot,
            version=plantilla.version,
            fecha_creacion=plantilla.fecha_creacion,
        )
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {
                'uq_plantillas_nombre_version': (
                    f"Ya existe una plantilla '{plantilla.template_name}' con versión {plantilla.version}."
                ),
            })
        return self._a_entidad(orm)

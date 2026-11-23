# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
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
    """Implementación SQLAlchemy de ``PlantillaRepository``."""

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
        """Obtiene una plantilla por su PK. Retorna ``None`` si no existe."""
        orm = self.db.get(PlantillaModel, id_plantilla)
        return self._a_entidad(orm) if orm else None

    def existe_nombre(self, template_name: str) -> bool:
        """Indica si ya hay alguna plantilla registrada con ese nombre.

        Compara normalizando mayúsculas y espacios, igual que el trigger
        ``trg_fn_plantilla_version_incremental``: si la app comparara exacto y
        la BD normalizada, "Tilapia" y "tilapia" pasarían el chequeo de unicidad
        y la BD las uniría en la misma familia de versiones sin avisar.
        """
        return self.db.scalar(
            select(func.count(PlantillaModel.id_plantilla)).where(
                func.lower(func.trim(PlantillaModel.template_name))
                == func.lower(func.trim(template_name))
            )
        ) > 0

    def listar_todas(self) -> list[Plantilla]:
        """Retorna todas las plantillas ordenadas por nombre y versión desc."""
        rows = (
            self.db.query(PlantillaModel)
            .order_by(PlantillaModel.template_name, PlantillaModel.version.desc())
            .all()
        )
        return [self._a_entidad(r) for r in rows]

    def obtener_ultima_version(self, template_name: str) -> Optional[Plantilla]:
        """Retorna la versión vigente (la de mayor número) para ese nombre.

        INC-M09-03-122 (#317): RF-31 exige que "una actualización genere una
        nueva versión, no sobreescriba la original" -- eso implica que la
        versión anterior queda superada. Este método es lo que permite a
        RF-32 comprobar que la plantilla que se va a aplicar es la vigente.
        Compara igual que `existe_nombre` (normalizado, sin distinguir
        mayúsculas/espacios) para no divergir del trigger de la BD.
        """
        orm = (
            self.db.query(PlantillaModel)
            .filter(
                func.lower(func.trim(PlantillaModel.template_name))
                == func.lower(func.trim(template_name))
            )
            .order_by(PlantillaModel.version.desc())
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def guardar(self, plantilla: Plantilla) -> Plantilla:
        """Inserta una plantilla nueva. Hace ``flush``. El ``commit`` lo emite el use case."""
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

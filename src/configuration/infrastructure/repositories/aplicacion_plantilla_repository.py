"""Implementación SQLAlchemy del puerto :class:`AplicacionPlantillaRepository`."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.entities.aplicacion_plantilla import AplicacionPlantilla
from src.configuration.domain.repositories.aplicacion_plantilla_repository import AplicacionPlantillaRepository
from src.configuration.infrastructure.models.aplicacion_plantilla_model import AplicacionPlantillaModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyAplicacionPlantillaRepository(AplicacionPlantillaRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: AplicacionPlantillaModel) -> AplicacionPlantilla:
        return AplicacionPlantilla(
            id_aplicacion_plantilla=orm.id_aplicacion_plantilla,
            id_usuario=orm.id_usuario,
            id_plantilla=orm.id_plantilla,
            target_config=orm.target_config,
            before_snapshot=orm.before_snapshot,
            after_snapshot=orm.after_snapshot,
            fecha_aplicacion=orm.fecha_aplicacion,
        )

    def guardar(self, aplicacion: AplicacionPlantilla) -> AplicacionPlantilla:
        orm = AplicacionPlantillaModel(
            id_usuario=aplicacion.id_usuario,
            id_plantilla=aplicacion.id_plantilla,
            target_config=aplicacion.target_config,
            before_snapshot=aplicacion.before_snapshot,
            after_snapshot=aplicacion.after_snapshot,
            fecha_aplicacion=aplicacion.fecha_aplicacion,
        )
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {})
        return self._a_entidad(orm)

    def listar_todas(self) -> list[AplicacionPlantilla]:
        rows = (
            self.db.query(AplicacionPlantillaModel)
            .order_by(AplicacionPlantillaModel.fecha_aplicacion.desc())
            .all()
        )
        return [self._a_entidad(r) for r in rows]

"""Implementación SQLAlchemy del puerto VariableAmbientalRepository."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.entities.variable_ambiental import VariableAmbiental
from src.configuration.domain.repositories.variable_ambiental_repository import VariableAmbientalRepository
from src.configuration.infrastructure.models.variable_ambiental_model import VariableAmbientalModel


class SqlAlchemyVariableAmbientalRepository(VariableAmbientalRepository):
    def __init__(self, db: Session) -> None:
        self._db = db

    def obtener_por_id(self, id_variable_ambiental: int) -> Optional[VariableAmbiental]:
        orm = self._db.get(VariableAmbientalModel, id_variable_ambiental)
        if orm is None:
            return None
        return self._a_entidad(orm)

    def listar_activas(self) -> list[VariableAmbiental]:
        orms = (
            self._db.query(VariableAmbientalModel)
            .filter(VariableAmbientalModel.es_activo.is_(True))
            .order_by(VariableAmbientalModel.nombre)
            .all()
        )
        return [self._a_entidad(orm) for orm in orms]

    @staticmethod
    def _a_entidad(orm: VariableAmbientalModel) -> VariableAmbiental:
        return VariableAmbiental(
            id_variable_ambiental=orm.id_variable_ambiental,
            nombre=orm.nombre,
            unidad=orm.unidad,
            valor_fisico_min=orm.valor_fisico_min,
            valor_fisico_max=orm.valor_fisico_max,
            es_activo=orm.es_activo,
        )

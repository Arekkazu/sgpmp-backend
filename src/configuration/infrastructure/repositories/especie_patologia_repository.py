"""Implementación SQLAlchemy del puerto :class:`EspeciePatologiaRepository`.

Gestiona la tabla pivot ``modulo9.especies_patologias`` y el join con
``modulo9.patologias`` para listar patologías por especie.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.entities.especie_patologia import EspeciePatologia
from src.configuration.domain.repositories.especie_patologia_repository import EspeciePatologiaRepository
from src.configuration.domain.value_objects.nombre_patologia import NombrePatologia
from src.configuration.infrastructure.models.especie_patologia_model import EspeciePatologiaModel
from src.configuration.infrastructure.models.patologia_model import PatologiaModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyEspeciePatologiaRepository(EspeciePatologiaRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(pivot: EspeciePatologiaModel, patologia: PatologiaModel) -> EspeciePatologia:
        return EspeciePatologia(
            id_especies_patologias=pivot.id_especies_patologias,
            id_patologia=pivot.id_patologia,
            id_especie=pivot.id_especie,
            nombre=NombrePatologia(patologia.nombre),
            descripcion=patologia.descripcion,
            es_activo=patologia.es_activo,
            fecha_actualizacion=patologia.fecha_actualizacion,
        )

    def obtener_por_especie_y_patologia(
        self, id_especie: int, id_patologia: int
    ) -> Optional[EspeciePatologia]:
        row = (
            self.db.query(EspeciePatologiaModel, PatologiaModel)
            .join(PatologiaModel, PatologiaModel.id_patologia == EspeciePatologiaModel.id_patologia)
            .filter(
                EspeciePatologiaModel.id_especie == id_especie,
                EspeciePatologiaModel.id_patologia == id_patologia,
            )
            .first()
        )
        if row is None:
            return None
        pivot, pat = row
        return self._a_entidad(pivot, pat)

    def listar_por_especie(
        self, id_especie: int, *, solo_activas: bool = False
    ) -> list[EspeciePatologia]:
        query = (
            self.db.query(EspeciePatologiaModel, PatologiaModel)
            .join(PatologiaModel, PatologiaModel.id_patologia == EspeciePatologiaModel.id_patologia)
            .filter(EspeciePatologiaModel.id_especie == id_especie)
        )
        if solo_activas:
            query = query.filter(PatologiaModel.es_activo.is_(True))
        return [
            self._a_entidad(pivot, pat)
            for pivot, pat in query.order_by(PatologiaModel.nombre).all()
        ]

    def asociar(self, id_especie: int, id_patologia: int) -> EspeciePatologia:
        pivot = EspeciePatologiaModel(id_especie=id_especie, id_patologia=id_patologia)
        try:
            self.db.add(pivot)
            self.db.flush()
            self.db.refresh(pivot)
        except Exception as exc:
            raise_from_db_error(exc, {
                "uq_especie_patologia": (
                    "La patología ya está asociada a esta especie."
                ),
            })
        pat = self.db.get(PatologiaModel, id_patologia)
        return self._a_entidad(pivot, pat)

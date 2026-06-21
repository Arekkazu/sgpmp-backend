"""Implementación SQLAlchemy del puerto UmbralAmbientalRepository."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.configuration.domain.entities.nivel_alerta_ambiental import NivelAlertaAmbiental
from src.configuration.domain.entities.umbral_ambiental import UmbralAmbiental
from src.configuration.domain.repositories.umbral_ambiental_repository import UmbralAmbientalRepository
from src.configuration.domain.value_objects.nivel_alerta import NivelAlerta
from src.configuration.infrastructure.models.nivel_alerta_ambiental_model import NivelAlertaAmbientalModel
from src.configuration.infrastructure.models.umbral_ambiental_model import UmbralAmbientalModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyUmbralAmbientalRepository(UmbralAmbientalRepository):
    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------

    def obtener_por_id(self, id_umbral_ambiental: int) -> Optional[UmbralAmbiental]:
        orm = self._db.get(UmbralAmbientalModel, id_umbral_ambiental)
        return self._a_entidad(orm) if orm else None

    def obtener_por_especie_y_variable(
        self, id_especie: int, id_variable_ambiental: int
    ) -> Optional[UmbralAmbiental]:
        stmt = select(UmbralAmbientalModel).where(
            UmbralAmbientalModel.id_especie == id_especie,
            UmbralAmbientalModel.id_variable_ambiental == id_variable_ambiental,
        )
        orm = self._db.scalars(stmt).first()
        return self._a_entidad(orm) if orm else None

    def listar_por_especie(
        self, id_especie: int, *, solo_activas: bool = False
    ) -> list[UmbralAmbiental]:
        stmt = select(UmbralAmbientalModel).where(
            UmbralAmbientalModel.id_especie == id_especie
        )
        if solo_activas:
            stmt = stmt.where(UmbralAmbientalModel.es_activo.is_(True))
        stmt = stmt.order_by(UmbralAmbientalModel.id_variable_ambiental)
        rows = self._db.scalars(stmt).all()
        return [self._a_entidad(r) for r in rows]

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------

    def guardar(self, umbral: UmbralAmbiental) -> UmbralAmbiental:
        try:
            orm = UmbralAmbientalModel(
                id_especie=umbral.id_especie,
                id_variable_ambiental=umbral.id_variable_ambiental,
                id_usuario=umbral.id_usuario,
                unidad_medida=umbral.unidad_medida,
                valor_min=umbral.valor_min,
                valor_max=umbral.valor_max,
                es_activo=umbral.es_activo,
                fecha_actualizacion=umbral.fecha_actualizacion,
            )
            self._db.add(orm)
            self._db.flush()

            for n in umbral.niveles:
                nivel_orm = NivelAlertaAmbientalModel(
                    id_umbral_ambiental=orm.id_umbral_ambiental,
                    nivel=n.nivel.value,
                    limite_inferior=n.limite_inferior,
                    limite_superior=n.limite_superior,
                )
                self._db.add(nivel_orm)

            self._db.flush()
            self._db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def actualizar(self, umbral: UmbralAmbiental) -> UmbralAmbiental:
        try:
            orm = self._db.get(UmbralAmbientalModel, umbral.id_umbral_ambiental)
            orm.valor_min = umbral.valor_min
            orm.valor_max = umbral.valor_max
            orm.es_activo = umbral.es_activo
            orm.fecha_actualizacion = umbral.fecha_actualizacion
            orm.id_usuario = umbral.id_usuario

            # Reemplazar niveles (delete-then-insert via cascade)
            for nivel_orm in list(orm.niveles):
                self._db.delete(nivel_orm)
            self._db.flush()

            for n in umbral.niveles:
                nivel_orm = NivelAlertaAmbientalModel(
                    id_umbral_ambiental=orm.id_umbral_ambiental,
                    nivel=n.nivel.value,
                    limite_inferior=n.limite_inferior,
                    limite_superior=n.limite_superior,
                )
                self._db.add(nivel_orm)

            self._db.flush()
            self._db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    # ------------------------------------------------------------------
    # Mapeo ORM → entidad
    # ------------------------------------------------------------------

    @staticmethod
    def _a_entidad(orm: UmbralAmbientalModel) -> UmbralAmbiental:
        niveles = [
            NivelAlertaAmbiental(
                nivel=NivelAlerta(n.nivel),
                limite_inferior=n.limite_inferior,
                limite_superior=n.limite_superior,
            )
            for n in orm.niveles
        ]
        return UmbralAmbiental(
            id_umbral_ambiental=orm.id_umbral_ambiental,
            id_especie=orm.id_especie,
            id_variable_ambiental=orm.id_variable_ambiental,
            unidad_medida=orm.unidad_medida,
            valor_min=orm.valor_min,
            valor_max=orm.valor_max,
            es_activo=orm.es_activo,
            niveles=niveles,
            fecha_actualizacion=orm.fecha_actualizacion,
            id_usuario=orm.id_usuario,
        )

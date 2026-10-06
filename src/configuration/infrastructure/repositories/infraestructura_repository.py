"""Implementación SQLAlchemy del puerto ``InfraestructuraRepository``."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.entities.infraestructura import Infraestructura
from src.configuration.domain.repositories.infraestructura_repository import InfraestructuraRepository
from src.configuration.domain.value_objects.nombre_infraestructura import NombreInfraestructura
from src.configuration.domain.value_objects.superficie import Superficie
from src.configuration.infrastructure.models.infraestructura_model import InfraestructuraModel
from src.shared.db_error_translator import raise_from_db_error
from src.shared.rehidratar import rehidratar


class SqlAlchemyInfraestructuraRepository(InfraestructuraRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: InfraestructuraModel) -> Infraestructura:
        return Infraestructura(
            id_infraestructura=orm.id_infraestructura,
            nombre=rehidratar(NombreInfraestructura, orm.nombre),
            tipo=orm.tipo,
            superficie=rehidratar(Superficie, Decimal(str(orm.superficie))),
            id_finca=orm.id_finca,
            descripcion=orm.descripcion,
            es_activo=orm.es_activo,
            fecha_actualizacion=orm.fecha_actualizacion,
            id_especie=orm.id_especie,
            tipo_modelo_asignado=orm.tipo_modelo_asignado,
        )

    def obtener_por_id(
        self,
        id_infraestructura: int,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
        bloquear: bool = False,
    ) -> Optional[Infraestructura]:
        orm = self.db.get(
            InfraestructuraModel, id_infraestructura, with_for_update=bloquear, populate_existing=bloquear,
        )
        if orm is None:
            return None
        if ids_fincas_permitidas is not None and orm.id_finca not in ids_fincas_permitidas:
            return None
        return self._a_entidad(orm)

    def guardar(self, infraestructura: Infraestructura) -> Infraestructura:
        orm = InfraestructuraModel(
            nombre=infraestructura.nombre.valor,
            tipo=infraestructura.tipo,
            superficie=infraestructura.superficie.valor,
            id_finca=infraestructura.id_finca,
            descripcion=infraestructura.descripcion,
            es_activo=infraestructura.es_activo,
            fecha_actualizacion=infraestructura.fecha_actualizacion,
            id_especie=infraestructura.id_especie,
            tipo_modelo_asignado=infraestructura.tipo_modelo_asignado,
        )
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {
                "uq_infraestructura_nombre": (
                    f"Ya existe un área denominada '{infraestructura.nombre.valor}' en esta finca."
                ),
            })
        return self._a_entidad(orm)

    def actualizar(self, infraestructura: Infraestructura) -> Infraestructura:
        orm = self.db.get(InfraestructuraModel, infraestructura.id_infraestructura)
        orm.nombre = infraestructura.nombre.valor
        orm.tipo = infraestructura.tipo
        orm.superficie = infraestructura.superficie.valor
        orm.descripcion = infraestructura.descripcion
        orm.es_activo = infraestructura.es_activo
        orm.fecha_actualizacion = infraestructura.fecha_actualizacion
        orm.id_especie = infraestructura.id_especie
        orm.tipo_modelo_asignado = infraestructura.tipo_modelo_asignado
        try:
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {
                "uq_infraestructura_nombre": (
                    f"Ya existe un área denominada '{infraestructura.nombre.valor}' en esta finca."
                ),
            })
        return self._a_entidad(orm)

    def listar_por_finca(
        self,
        id_finca: int,
        *,
        solo_activas: bool = False,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> list[Infraestructura]:
        if ids_fincas_permitidas is not None and id_finca not in ids_fincas_permitidas:
            return []
        query = self.db.query(InfraestructuraModel).filter(InfraestructuraModel.id_finca == id_finca)
        if solo_activas:
            query = query.filter(InfraestructuraModel.es_activo.is_(True))
        return [self._a_entidad(orm) for orm in query.order_by(InfraestructuraModel.nombre).all()]

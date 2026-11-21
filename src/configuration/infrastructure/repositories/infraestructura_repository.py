# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-22 RF-20: especies del área en la puente y capacidad_maxima derivada |
"""Implementación SQLAlchemy del puerto ``InfraestructuraRepository``."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.entities.infraestructura import Infraestructura
from src.configuration.domain.repositories.infraestructura_repository import InfraestructuraRepository
from src.configuration.domain.value_objects.nombre_infraestructura import NombreInfraestructura
from src.configuration.domain.value_objects.superficie import Superficie
from src.configuration.domain.services.capacidad_area import EspecieDelArea, capacidad_efectiva
from src.configuration.infrastructure.models.especie_model import EspecieModel
from src.configuration.infrastructure.models.infraestructura_model import (
    InfraestructuraEspecieModel,
    InfraestructuraModel,
)
from src.shared.db_error_translator import raise_from_db_error
from src.shared.rehidratar import rehidratar


class SqlAlchemyInfraestructuraRepository(InfraestructuraRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def especies_del_area(self, orm: InfraestructuraModel) -> list[EspecieDelArea]:
        ids = [fila.id_especie for fila in orm.especies]
        if not ids:
            return []
        por_id = {
            e.id_especie: e
            for e in self.db.query(EspecieModel).filter(EspecieModel.id_especie.in_(ids)).all()
        }
        return [
            EspecieDelArea(
                id_especie=i,
                nombre=por_id[i].nombre,
                grupo_manejo=por_id[i].grupo_manejo,
                densidad=por_id[i].densidad_maxima_por_especie,
            )
            for i in ids
        ]

    def _a_entidad(self, orm: InfraestructuraModel) -> Infraestructura:
        superficie = Decimal(str(orm.superficie))
        return Infraestructura(
            id_infraestructura=orm.id_infraestructura,
            nombre=rehidratar(NombreInfraestructura, orm.nombre),
            tipo=orm.tipo,
            superficie=rehidratar(Superficie, superficie),
            id_finca=orm.id_finca,
            descripcion=orm.descripcion,
            es_activo=orm.es_activo,
            fecha_actualizacion=orm.fecha_actualizacion,
            id_especies=[fila.id_especie for fila in orm.especies],
            tipo_modelo_asignado=orm.tipo_modelo_asignado,
            nivel_criticidad=orm.nivel_criticidad,
            capacidad_maxima=capacidad_efectiva(superficie, self.especies_del_area(orm)),
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
            tipo_modelo_asignado=infraestructura.tipo_modelo_asignado,
            nivel_criticidad=infraestructura.nivel_criticidad,
            especies=[InfraestructuraEspecieModel(id_especie=i) for i in infraestructura.id_especies],
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
        orm.tipo_modelo_asignado = infraestructura.tipo_modelo_asignado
        orm.nivel_criticidad = infraestructura.nivel_criticidad
        # Diferencia, no delete-then-insert: la fila conserva su fecha de asociación
        # (el downgrade de DB-06 toma la más antigua como especie principal).
        nuevas = list(dict.fromkeys(infraestructura.id_especies))
        for fila in [f for f in orm.especies if f.id_especie not in nuevas]:
            orm.especies.remove(fila)
        actuales = {f.id_especie for f in orm.especies}
        orm.especies.extend(InfraestructuraEspecieModel(id_especie=i) for i in nuevas if i not in actuales)
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

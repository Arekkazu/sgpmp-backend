"""Implementación SQLAlchemy del puerto :class:`CicloBiologicoRepository`."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.configuration.domain.entities.ciclo_biologico import CicloBiologico
from src.configuration.domain.repositories.ciclo_biologico_repository import CicloBiologicoRepository
from src.configuration.domain.value_objects.duracion_dias import DuracionDias
from src.configuration.domain.value_objects.nombre_etapa import NombreEtapa
from src.configuration.infrastructure.models.ciclo_biologico_model import CicloBiologicoModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyCicloBiologicoRepository(CicloBiologicoRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: CicloBiologicoModel) -> CicloBiologico:
        return CicloBiologico(
            id_ciclo_biologico=orm.id_ciclo_biologico,
            nombre=NombreEtapa(orm.nombre),
            descripcion=orm.descripcion,
            duracion_dias=DuracionDias(orm.duracion_dias),
            id_especie=orm.id_especie,
            es_activo=orm.es_activo,
            fecha_actualizacion=orm.fecha_actualizacion,
        )

    def obtener_por_id(self, id_ciclo_biologico: int) -> Optional[CicloBiologico]:
        orm = self.db.get(CicloBiologicoModel, id_ciclo_biologico)
        return self._a_entidad(orm) if orm else None

    def obtener_por_nombre_y_especie(
        self, nombre: NombreEtapa, id_especie: int
    ) -> Optional[CicloBiologico]:
        orm = (
            self.db.query(CicloBiologicoModel)
            .filter(
                func.lower(CicloBiologicoModel.nombre) == nombre.normalizado(),
                CicloBiologicoModel.id_especie == id_especie,
            )
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def listar_por_especie(
        self, id_especie: int, *, solo_activas: bool = False
    ) -> list[CicloBiologico]:
        query = self.db.query(CicloBiologicoModel).filter(
            CicloBiologicoModel.id_especie == id_especie
        )
        if solo_activas:
            query = query.filter(CicloBiologicoModel.es_activo.is_(True))
        return [
            self._a_entidad(orm)
            for orm in query.order_by(CicloBiologicoModel.nombre).all()
        ]

    def guardar(self, ciclo: CicloBiologico) -> CicloBiologico:
        orm = CicloBiologicoModel(
            nombre=ciclo.nombre.valor,
            descripcion=ciclo.descripcion,
            duracion_dias=ciclo.duracion_dias.valor,
            id_especie=ciclo.id_especie,
            es_activo=ciclo.es_activo,
        )
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {})
        return self._a_entidad(orm)

    def actualizar(self, ciclo: CicloBiologico) -> CicloBiologico:
        orm = self.db.get(CicloBiologicoModel, ciclo.id_ciclo_biologico)
        orm.nombre = ciclo.nombre.valor
        orm.descripcion = ciclo.descripcion
        orm.duracion_dias = ciclo.duracion_dias.valor
        orm.es_activo = ciclo.es_activo
        orm.fecha_actualizacion = ciclo.fecha_actualizacion
        try:
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {})
        return self._a_entidad(orm)

    def desactivar_todos_por_especie(self, id_especie: int) -> None:
        try:
            self.db.query(CicloBiologicoModel).filter(
                CicloBiologicoModel.id_especie == id_especie,
                CicloBiologicoModel.es_activo.is_(True),
            ).update({'es_activo': False}, synchronize_session='fetch')
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc, {})

    def guardar_desde_snapshot(self, datos: dict, id_especie: int) -> None:
        orm = CicloBiologicoModel(
            nombre=datos['nombre'],
            descripcion=datos.get('descripcion'),
            duracion_dias=int(datos['duracion_dias']),
            id_especie=id_especie,
            es_activo=True,
        )
        try:
            self.db.add(orm)
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc, {})

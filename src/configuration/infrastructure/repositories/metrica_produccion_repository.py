"""Implementación SQLAlchemy del puerto :class:`MetricaProduccionRepository`."""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.configuration.domain.entities.metrica_produccion import MetricaProduccion
from src.configuration.domain.repositories.metrica_produccion_repository import MetricaProduccionRepository
from src.configuration.domain.value_objects.aplica_tipo_activo import AplicaTipoActivo
from src.configuration.domain.value_objects.nombre_metrica import NombreMetrica
from src.configuration.domain.value_objects.tipo_medicion import TipoMedicion
from src.configuration.infrastructure.models.metrica_produccion_model import MetricaProduccionModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyMetricaProduccionRepository(MetricaProduccionRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: MetricaProduccionModel) -> MetricaProduccion:
        return MetricaProduccion(
            id_metrica_produccion=orm.id_metrica_produccion,
            nombre=NombreMetrica(orm.nombre),
            unidad_medida=orm.unidad_medida,
            tipo_medicion=TipoMedicion(orm.tipo_medicion),
            aplica_a_tipo_activo=AplicaTipoActivo(orm.aplica_a_tipo_activo),
            id_especie=orm.id_especie,
            es_activo=orm.es_activo,
            fecha_actualizacion=orm.fecha_actualizacion,
        )

    def obtener_por_id(self, id_metrica_produccion: int) -> Optional[MetricaProduccion]:
        orm = self.db.get(MetricaProduccionModel, id_metrica_produccion)
        return self._a_entidad(orm) if orm else None

    def obtener_por_nombre_y_especie(
        self, nombre: NombreMetrica, id_especie: int
    ) -> Optional[MetricaProduccion]:
        orm = (
            self.db.query(MetricaProduccionModel)
            .filter(
                func.lower(MetricaProduccionModel.nombre) == nombre.normalizado(),
                MetricaProduccionModel.id_especie == id_especie,
            )
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def listar_por_especie(
        self, id_especie: int, *, solo_activas: bool = False
    ) -> list[MetricaProduccion]:
        query = self.db.query(MetricaProduccionModel).filter(
            MetricaProduccionModel.id_especie == id_especie
        )
        if solo_activas:
            query = query.filter(MetricaProduccionModel.es_activo.is_(True))
        return [
            self._a_entidad(orm)
            for orm in query.order_by(MetricaProduccionModel.nombre).all()
        ]

    def guardar(self, metrica: MetricaProduccion) -> MetricaProduccion:
        orm = MetricaProduccionModel(
            nombre=metrica.nombre.valor,
            unidad_medida=metrica.unidad_medida,
            tipo_medicion=metrica.tipo_medicion.value,
            aplica_a_tipo_activo=metrica.aplica_a_tipo_activo.value,
            id_especie=metrica.id_especie,
            es_activo=metrica.es_activo,
            # tiene_estado es campo legacy de M04 — se inserta False por defecto
            tiene_estado=False,
        )
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {})
        return self._a_entidad(orm)

    def actualizar(self, metrica: MetricaProduccion) -> MetricaProduccion:
        orm = self.db.get(MetricaProduccionModel, metrica.id_metrica_produccion)
        orm.nombre = metrica.nombre.valor
        orm.unidad_medida = metrica.unidad_medida
        orm.tipo_medicion = metrica.tipo_medicion.value
        orm.aplica_a_tipo_activo = metrica.aplica_a_tipo_activo.value
        orm.es_activo = metrica.es_activo
        orm.fecha_actualizacion = metrica.fecha_actualizacion
        try:
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {})
        return self._a_entidad(orm)

    def desactivar_todas_por_especie(self, id_especie: int) -> None:
        try:
            self.db.query(MetricaProduccionModel).filter(
                MetricaProduccionModel.id_especie == id_especie,
                MetricaProduccionModel.es_activo.is_(True),
            ).update({'es_activo': False}, synchronize_session='fetch')
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc, {})

    def guardar_desde_snapshot(self, datos: dict, id_especie: int, id_usuario: int) -> None:
        orm = MetricaProduccionModel(
            nombre=datos['nombre'],
            unidad_medida=datos['unidad_medida'],
            tipo_medicion=datos['tipo_medicion'],
            aplica_a_tipo_activo=datos['aplica_a_tipo_activo'],
            id_especie=id_especie,
            es_activo=True,
            tiene_estado=False,
        )
        try:
            self.db.add(orm)
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc, {})

"""Adapter de ``ParametrosEspeciePort`` que lee densidad máxima, parámetros y métricas
productivas de M09.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.biological_assets.domain.repositories.parametros_especie_port import MetricaProductiva, ParametroEspecie, ParametrosEspeciePort
from src.configuration.infrastructure.models.especie_model import EspecieModel
from src.configuration.infrastructure.models.metrica_produccion_model import MetricaProduccionModel

# El campo aplica_a_tipo_activo usa 'LOTE' para activos poblacionales
_TIPO_ACTIVO_A_LOTE = {
    'INDIVIDUAL': 'INDIVIDUAL',
    'POBLACIONAL': 'LOTE',
}


def _a_parametro(r: MetricaProduccionModel) -> ParametroEspecie:
    return ParametroEspecie(
        nombre=r.nombre,
        tipo_medicion=r.tipo_medicion,
        aplica_a_tipo_activo=r.aplica_a_tipo_activo,
        tipo_dato=r.tipo_dato,
        es_obligatorio=r.es_obligatorio,
        valor_min=r.valor_min,
        valor_max=r.valor_max,
        unidad_medida=r.unidad_medida,
    )


def _a_metrica(r: MetricaProduccionModel) -> MetricaProductiva:
    return MetricaProductiva(
        id_metrica_produccion=r.id_metrica_produccion,
        tipo_producto=r.nombre,
        unidad_medida=r.unidad_medida,
        aplica_a_tipo_activo=r.aplica_a_tipo_activo,
        tipo_medicion=r.tipo_medicion,
        tipo_dato=r.tipo_dato,
        valor_min=r.valor_min,
        valor_max=r.valor_max,
    )


class ParametrosEspecieM09Adapter(ParametrosEspeciePort):
    """Consulta modulo9.metricas_produccion para validar atributos_dinamicos y rangos de medición."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_densidad_maxima(self, id_especie: int) -> Optional[Decimal]:
        row = self.db.get(EspecieModel, id_especie)
        if row is None or not row.es_activo:
            return None
        return row.densidad_maxima_por_especie

    def listar_por_especie(self, id_especie: int, tipo_activo: str) -> list[ParametroEspecie]:
        tipo_db = _TIPO_ACTIVO_A_LOTE.get(tipo_activo, tipo_activo)
        rows = (
            self.db.query(MetricaProduccionModel)
            .filter(
                MetricaProduccionModel.id_especie == id_especie,
                MetricaProduccionModel.es_activo.is_(True),
                MetricaProduccionModel.aplica_a_tipo_activo.in_([tipo_db, 'AMBOS']),
            )
            .all()
        )
        return [_a_parametro(r) for r in rows]

    def obtener_por_tipo_medicion(
        self, id_especie: int, tipo_medicion: str, tipo_activo: str
    ) -> Optional[ParametroEspecie]:
        tipo_db = _TIPO_ACTIVO_A_LOTE.get(tipo_activo, tipo_activo)
        row = (
            self.db.query(MetricaProduccionModel)
            .filter(
                MetricaProduccionModel.id_especie == id_especie,
                MetricaProduccionModel.es_activo.is_(True),
                MetricaProduccionModel.tipo_medicion == tipo_medicion,
                MetricaProduccionModel.aplica_a_tipo_activo.in_([tipo_db, 'AMBOS']),
            )
            .first()
        )
        return _a_parametro(row) if row is not None else None

    def obtener_metrica_productiva(
        self, id_metrica_produccion: int, id_especie: int, tipo_activo: str
    ) -> Optional[MetricaProductiva]:
        row = self._metricas_productivas(id_especie, tipo_activo).filter(
            MetricaProduccionModel.id_metrica_produccion == id_metrica_produccion,
        ).first()
        return _a_metrica(row) if row is not None else None

    def listar_metricas_productivas(self, id_especie: int, tipo_activo: str) -> list[MetricaProductiva]:
        rows = self._metricas_productivas(id_especie, tipo_activo).order_by(MetricaProduccionModel.nombre).all()
        return [_a_metrica(r) for r in rows]

    def _metricas_productivas(self, id_especie: int, tipo_activo: str):
        tipo_db = _TIPO_ACTIVO_A_LOTE.get(tipo_activo, tipo_activo)
        return self.db.query(MetricaProduccionModel).filter(
            MetricaProduccionModel.id_especie == id_especie,
            MetricaProduccionModel.es_activo.is_(True),
            MetricaProduccionModel.aplica_a_tipo_activo.in_([tipo_db, 'AMBOS']),
        )

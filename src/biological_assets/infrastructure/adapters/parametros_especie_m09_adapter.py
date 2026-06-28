from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.biological_assets.domain.repositories.parametros_especie_port import ParametroEspecie, ParametrosEspeciePort
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
        valor_min=r.valor_min,
        valor_max=r.valor_max,
    )


class ParametrosEspecieM09Adapter(ParametrosEspeciePort):
    """Consulta modulo9.metricas_produccion para validar atributos_dinamicos y rangos de medición."""

    def __init__(self, db: Session) -> None:
        self.db = db

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

from __future__ import annotations

from sqlalchemy.orm import Session

from src.biological_assets.domain.repositories.parametros_especie_port import ParametroEspecie, ParametrosEspeciePort
from src.configuration.infrastructure.models.metrica_produccion_model import MetricaProduccionModel

# El campo aplica_a_tipo_activo usa 'LOTE' para activos poblacionales
_TIPO_ACTIVO_A_LOTE = {
    'INDIVIDUAL': 'INDIVIDUAL',
    'POBLACIONAL': 'LOTE',
}


class ParametrosEspecieM09Adapter(ParametrosEspeciePort):
    """Consulta modulo9.metricas_produccion para validar atributos_dinamicos."""

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
        return [
            ParametroEspecie(
                nombre=r.nombre,
                tipo_medicion=r.tipo_medicion,
                aplica_a_tipo_activo=r.aplica_a_tipo_activo,
            )
            for r in rows
        ]

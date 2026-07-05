from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.biological_assets.domain.repositories.infraestructura_consulta_port import (
    InfraestructuraConsulta,
    InfraestructuraConsultaPort,
)
from src.configuration.infrastructure.models.infraestructura_model import InfraestructuraModel


class InfraestructuraM09Adapter(InfraestructuraConsultaPort):
    """Consulta directamente modulo9.infraestructuras para verificar existencia y estado."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_consulta(orm: InfraestructuraModel) -> InfraestructuraConsulta:
        return InfraestructuraConsulta(
            id_infraestructura=orm.id_infraestructura,
            nombre=orm.nombre,
            tipo=orm.tipo,
            es_activo=orm.es_activo,
            superficie=Decimal(str(orm.superficie)) if orm.superficie is not None else None,
            id_finca=orm.id_finca,
            capacidad_maxima=orm.capacidad_maxima,
            id_especie=orm.id_especie,
        )

    def obtener_activa(self, id_infraestructura: int) -> Optional[InfraestructuraConsulta]:
        orm = self.db.get(InfraestructuraModel, id_infraestructura)
        if orm is None or not orm.es_activo:
            return None
        return self._a_consulta(orm)

    def listar_activas(self, excluir_id: Optional[int] = None) -> list[InfraestructuraConsulta]:
        q = self.db.query(InfraestructuraModel).filter(InfraestructuraModel.es_activo.is_(True))
        if excluir_id is not None:
            q = q.filter(InfraestructuraModel.id_infraestructura != excluir_id)
        return [self._a_consulta(orm) for orm in q.all()]

    def calcular_ocupacion(self, id_infraestructura: int) -> int:
        """Suma de individuos activos en la infraestructura (INDIVIDUAL cuenta 1, POBLACIONAL suma cantidad_actual)."""
        row = self.db.execute(
            text(
                'SELECT COALESCE(SUM(CASE WHEN ab.tipo = :ind THEN 1 '
                '  ELSE COALESCE(dp.cantidad_actual, 0) END), 0) AS total '
                'FROM modulo2.activos_biologicos ab '
                'LEFT JOIN modulo2.detalles_activos_biologicos_poblacionales dp '
                '  ON dp.id_activo_biologico = ab.id_activo_biologico '
                'WHERE ab.id_infraestructura = :id_infra '
                '  AND ab.id_estado NOT IN (5, 6)'  # excluye CERRADO y BAJA
            ),
            {'id_infra': id_infraestructura, 'ind': 'INDIVIDUAL'},
        ).fetchone()
        return int(row.total) if row else 0

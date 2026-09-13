from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import SensorEnInfraestructura
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

    def listar_sensores_activos(self, id_infraestructura: int) -> list[SensorEnInfraestructura]:
        """Sensores con asociación de área activa (RF-22) en la infraestructura dada."""
        rows = self.db.execute(
            text(
                'SELECT s.id_sensores, s.nombre, s.categoria, s.id_dispositivo_iot, saa.punto_instalacion '
                'FROM modulo9.sensores_areas_asociadas saa '
                'JOIN modulo9.sensores s ON s.id_sensores = saa.id_sensor '
                'WHERE saa.id_infraestructura = :id_infra '
                '  AND saa.tiene_estado = true '
                '  AND s.es_activo = true'
            ),
            {'id_infra': id_infraestructura},
        ).fetchall()
        return [
            SensorEnInfraestructura(
                id_sensor=row.id_sensores,
                nombre=row.nombre,
                id_dispositivo_iot=row.id_dispositivo_iot,
                punto_instalacion=row.punto_instalacion,
                categoria=row.categoria,
            )
            for row in rows
        ]

    def es_tipo_compatible(self, tipo_infraestructura: str, id_especie: int) -> bool:
        total_reglas = self.db.execute(
            text(
                'SELECT COUNT(*) FROM modulo9.compatibilidades_tipo_area_especie c '
                'JOIN modulo9.tipos_area ta ON ta.id_tipo_area = c.id_tipo_area '
                'WHERE ta.nombre = :tipo'
            ),
            {'tipo': tipo_infraestructura},
        ).scalar()
        if not total_reglas:
            return True  # sin regla configurada para este tipo -> sin restriccion todavia

        return bool(
            self.db.execute(
                text(
                    'SELECT EXISTS ('
                    '  SELECT 1 FROM modulo9.compatibilidades_tipo_area_especie c '
                    '  JOIN modulo9.tipos_area ta ON ta.id_tipo_area = c.id_tipo_area '
                    '  WHERE ta.nombre = :tipo AND c.id_especie = :id_especie'
                    ')'
                ),
                {'tipo': tipo_infraestructura, 'id_especie': id_especie},
            ).scalar()
        )

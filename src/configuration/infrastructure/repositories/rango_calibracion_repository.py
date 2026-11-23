# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Implementación SQLAlchemy del puerto ``RangoCalibracionRepository`` (RF-24)."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.entities.rango_calibracion import RangoCalibracion
from src.configuration.domain.repositories.rango_calibracion_repository import RangoCalibracionRepository
from src.configuration.infrastructure.models.rango_calibracion_model import RangoCalibracionModel


class SqlAlchemyRangoCalibracionRepository(RangoCalibracionRepository):
    """Implementación SQLAlchemy de ``RangoCalibracionRepository``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: RangoCalibracionModel) -> RangoCalibracion:
        return RangoCalibracion(
            categoria=orm.categoria,
            valor_min=Decimal(str(orm.valor_min)),
            valor_max=Decimal(str(orm.valor_max)),
        )

    def obtener_por_categoria(self, categoria: str) -> Optional[RangoCalibracion]:
        """Rango de calibración del tipo de sensor, o ``None`` si no está configurado."""
        orm = (
            self.db.query(RangoCalibracionModel)
            .filter(RangoCalibracionModel.categoria == categoria)
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def listar(self) -> list[RangoCalibracion]:
        """Todos los rangos de calibración configurados."""
        orms = self.db.query(RangoCalibracionModel).order_by(RangoCalibracionModel.categoria).all()
        return [self._a_entidad(orm) for orm in orms]

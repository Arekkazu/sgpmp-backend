# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-03 | Arekkazu | RF-72: bandeja de inferencias por evaluar (la pantalla mostraba datos de ejemplo) |
# | 2026-11-03 | Claude   | RF-72: página e indicadores en una sola operación |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de la bandeja de retroalimentación."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.prediction.domain.entities.bandeja_retroalimentacion import (
    FiltrosBandejaRetroalimentacion, IndicadoresBandejaRetroalimentacion, InferenciaPorEvaluar,
)


class BandejaRetroalimentacionRepository(ABC):
    """Puerto de consulta de la bandeja de retroalimentación."""

    @abstractmethod
    def consultar(
        self, filtros: FiltrosBandejaRetroalimentacion,
    ) -> tuple[list[InferenciaPorEvaluar], int, IndicadoresBandejaRetroalimentacion]:
        """Una página de la bandeja (pendientes primero, luego por fecha), el total con el filtro y
        cuántas hay en cada estado sin contar el filtro de estado. Juntos porque comparten el mismo
        cálculo, que es lo caro."""

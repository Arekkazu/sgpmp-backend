# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-03 | Arekkazu | RF-72: bandeja de inferencias por evaluar (la pantalla mostraba datos de ejemplo) |
from __future__ import annotations

from abc import ABC, abstractmethod

from src.prediction.domain.entities.bandeja_retroalimentacion import (
    FiltrosBandejaRetroalimentacion, IndicadoresBandejaRetroalimentacion, InferenciaPorEvaluar,
)


class BandejaRetroalimentacionRepository(ABC):

    @abstractmethod
    def listar(self, filtros: FiltrosBandejaRetroalimentacion) -> tuple[list[InferenciaPorEvaluar], int]:
        """Una página de la bandeja (pendientes primero, luego por fecha) y el total con el filtro."""

    @abstractmethod
    def indicadores(self, filtros: FiltrosBandejaRetroalimentacion) -> IndicadoresBandejaRetroalimentacion:
        """Cuántas hay en cada estado con los mismos filtros, sin contar el de estado."""

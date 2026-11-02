# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-29 | Arekkazu | PEND-456 RF-66/RF-68: monitor de predicción con datos reales       |
# | 2026-11-02 | Arekkazu | RF-66/RF-68: por_activo, las N más recientes de cada animal o lote |
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.prediction.domain.entities.monitor_prediccion import InferenciaMonitor, RiesgoContagioMonitor


class MonitorPrediccionRepository(ABC):

    @abstractmethod
    def listar_inferencias(
        self, *, ids_fincas: Optional[list[int]], tipo_modelo: Optional[str], nivel_riesgo: Optional[int],
        desde: Optional[datetime], hasta: Optional[datetime], limite: int, por_activo: Optional[int] = None,
    ) -> list[InferenciaMonitor]:
        """Más recientes primero; ``ids_fincas`` None = alcance global. Con ``por_activo``, las N más
        recientes de cada activo (los demás filtros se aplican sobre ellas) y ``limite`` no aplica."""

    @abstractmethod
    def listar_riesgo_contagio(
        self, *, ids_fincas: Optional[list[int]], nivel_riesgo: Optional[int],
        desde: Optional[datetime], hasta: Optional[datetime], limite: int, por_activo: Optional[int] = None,
    ) -> list[RiesgoContagioMonitor]:
        """Más recientes primero; ``ids_fincas`` None = alcance global. ``por_activo`` como en
        ``listar_inferencias``."""

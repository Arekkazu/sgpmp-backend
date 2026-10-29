# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-178-G57B RF-57: puerto de indicadores del sistema de alertas |
"""Puerto de los indicadores de estado del sistema de alertas (RF-57, Salida 3)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.telemetry.domain.entities.indicadores_alertas import FiltroIndicadoresAlertas, IndicadoresAlertas


class IndicadoresAlertasRepository(ABC):

    @abstractmethod
    def calcular(self, filtro: FiltroIndicadoresAlertas) -> IndicadoresAlertas:
        """Indicadores de las alertas operativas del alcance (fincas del usuario y área opcional)."""

    @abstractmethod
    def contar_vencidas_sin_atencion(self, filtro: FiltroIndicadoresAlertas) -> int:
        """Solo ``alertas_vencidas_sin_atencion``, para el dashboard de monitoreo."""

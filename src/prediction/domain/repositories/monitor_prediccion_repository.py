# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-29 | Arekkazu | PEND-456 RF-66/RF-68: monitor de predicción con datos reales       |
# | 2026-11-02 | Arekkazu | RF-66/RF-68: por_activo, las N más recientes de cada animal o lote |
# | 2026-11-02 | Arekkazu | AJF-10 RF-66: monitor paginado con filtro por animal o área, solo con alerta y sin pruebas |
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.prediction.domain.entities.monitor_prediccion import (
    IndicadoresInferencias, InferenciaMonitor, RiesgoContagioMonitor,
)


class MonitorPrediccionRepository(ABC):

    @abstractmethod
    def listar_inferencias(
        self, *, ids_fincas: Optional[list[int]], tipo_modelo: Optional[str], nivel_riesgo: Optional[int],
        desde: Optional[datetime], hasta: Optional[datetime], limite: int, por_activo: Optional[int] = None,
        id_activo_biologico: Optional[int] = None, id_infraestructura: Optional[int] = None,
        solo_con_alerta: bool = False, incluir_sombra: bool = True, desplazamiento: int = 0,
    ) -> list[InferenciaMonitor]:
        """Más recientes primero; ``ids_fincas`` None = alcance global. Con ``por_activo``, las N más
        recientes de cada activo (los demás filtros se aplican sobre ellas) y ``limite`` no aplica.
        AJF-10: filtro por animal o área, solo las que generaron alerta, sin las de prueba (sombra)
        y ``desplazamiento`` para paginar."""

    @abstractmethod
    def contar_inferencias(
        self, *, ids_fincas: Optional[list[int]], tipo_modelo: Optional[str], nivel_riesgo: Optional[int],
        desde: Optional[datetime], hasta: Optional[datetime], id_activo_biologico: Optional[int] = None,
        id_infraestructura: Optional[int] = None, solo_con_alerta: bool = False, incluir_sombra: bool = True,
    ) -> IndicadoresInferencias:
        """AJF-10: totales con los mismos filtros que ``listar_inferencias``."""

    @abstractmethod
    def listar_riesgo_contagio(
        self, *, ids_fincas: Optional[list[int]], nivel_riesgo: Optional[int],
        desde: Optional[datetime], hasta: Optional[datetime], limite: int, por_activo: Optional[int] = None,
    ) -> list[RiesgoContagioMonitor]:
        """Más recientes primero; ``ids_fincas`` None = alcance global. ``por_activo`` como en
        ``listar_inferencias``."""

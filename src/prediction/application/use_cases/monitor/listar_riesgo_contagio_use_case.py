# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-29 | Arekkazu | PEND-456 RF-66/RF-68: monitor de predicción con datos reales       |
# | 2026-11-02 | Arekkazu | RF-66/RF-68: por_activo, las N más recientes de cada animal o lote |
from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.prediction.application.use_cases.monitor.filtros_monitor import validar_filtros, validar_por_activo
from src.prediction.domain.entities.monitor_prediccion import RiesgoContagioMonitor
from src.prediction.domain.repositories.monitor_prediccion_repository import MonitorPrediccionRepository


class ListarRiesgoContagioUseCase:
    """RF-68: cálculos de riesgo de contagio por lote en el alcance del usuario."""

    def __init__(self, repo: MonitorPrediccionRepository) -> None:
        self._repo = repo

    def execute(
        self, *, ids_fincas: Optional[list[int]], nivel_riesgo: Optional[int] = None,
        desde: Optional[datetime] = None, hasta: Optional[datetime] = None, limite: int = 50,
        por_activo: Optional[int] = None,
    ) -> list[RiesgoContagioMonitor]:
        limite = validar_filtros(nivel_riesgo=nivel_riesgo, desde=desde, hasta=hasta, limite=limite)
        return self._repo.listar_riesgo_contagio(
            ids_fincas=ids_fincas, nivel_riesgo=nivel_riesgo, desde=desde, hasta=hasta, limite=limite,
            por_activo=validar_por_activo(por_activo),
        )

# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-29 | Arekkazu | PEND-456 RF-66/RF-68: monitor de predicción con datos reales       |
from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.prediction.application.use_cases.monitor.filtros_monitor import validar_filtros
from src.prediction.domain.entities.monitor_prediccion import InferenciaMonitor
from src.prediction.domain.repositories.monitor_prediccion_repository import MonitorPrediccionRepository


class ListarInferenciasUseCase:
    """RF-66: resultados del motor de inferencia en el alcance del usuario."""

    def __init__(self, repo: MonitorPrediccionRepository) -> None:
        self._repo = repo

    def execute(
        self, *, ids_fincas: Optional[list[int]], tipo_modelo: Optional[str] = None,
        nivel_riesgo: Optional[int] = None, desde: Optional[datetime] = None,
        hasta: Optional[datetime] = None, limite: int = 50,
    ) -> list[InferenciaMonitor]:
        limite = validar_filtros(
            tipo_modelo=tipo_modelo, nivel_riesgo=nivel_riesgo, desde=desde, hasta=hasta, limite=limite,
        )
        return self._repo.listar_inferencias(
            ids_fincas=ids_fincas, tipo_modelo=tipo_modelo, nivel_riesgo=nivel_riesgo,
            desde=desde, hasta=hasta, limite=limite,
        )

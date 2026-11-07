# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-29 | Arekkazu | PEND-456 RF-66/RF-68: monitor de predicción con datos reales       |
# | 2026-11-02 | Arekkazu | RF-66/RF-68: por_activo, las N más recientes de cada animal o lote |
# | 2026-11-02 | Arekkazu | AJF-10 RF-66: monitor paginado con filtro por animal o área, solo con alerta y sin pruebas |
from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.prediction.application.use_cases.monitor.filtros_monitor import validar_filtros, validar_por_activo
from src.prediction.domain.entities.monitor_prediccion import InferenciaMonitor
from src.prediction.domain.repositories.monitor_prediccion_repository import MonitorPrediccionRepository


class ListarInferenciasUseCase:
    """RF-66: resultados del motor de inferencia en el alcance del usuario."""

    def __init__(self, repo: MonitorPrediccionRepository) -> None:
        self._repo = repo

    def execute(
        self, *, ids_fincas: Optional[list[int]], tipo_modelo: Optional[str] = None,
        nivel_riesgo: Optional[int] = None, desde: Optional[datetime] = None,
        hasta: Optional[datetime] = None, limite: int = 50, por_activo: Optional[int] = None,
        id_activo_biologico: Optional[int] = None, id_infraestructura: Optional[int] = None,
        solo_con_alerta: bool = False, incluir_sombra: bool = True,
    ) -> list[InferenciaMonitor]:
        limite = validar_filtros(
            tipo_modelo=tipo_modelo, nivel_riesgo=nivel_riesgo, desde=desde, hasta=hasta, limite=limite,
        )
        return self._repo.listar_inferencias(
            ids_fincas=ids_fincas, tipo_modelo=tipo_modelo, nivel_riesgo=nivel_riesgo,
            desde=desde, hasta=hasta, limite=limite, por_activo=validar_por_activo(por_activo),
            id_activo_biologico=id_activo_biologico, id_infraestructura=id_infraestructura,
            solo_con_alerta=solo_con_alerta, incluir_sombra=incluir_sombra,
        )

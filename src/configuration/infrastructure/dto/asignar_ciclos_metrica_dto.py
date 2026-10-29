"""DTO de ``PUT /configuracion/metricas/{id}/ciclos-productivos`` (RF-43 E-04)."""
from __future__ import annotations

from pydantic import Field

from src.shared.base_dto import BaseDTO


class AsignarCiclosMetricaDTO(BaseDTO):
    """Ciclos productivos en los que la métrica queda habilitada; la lista reemplaza la anterior."""
    ids_ciclos_productivos: list[int] = Field(default_factory=list)

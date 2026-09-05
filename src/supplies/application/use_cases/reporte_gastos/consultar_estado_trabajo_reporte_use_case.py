"""Caso de uso: consultar el estado de un trabajo async de generación de reporte (RF-77).

Polling del cliente tras recibir un HTTP 202 con ``id_cola``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.shared.errors import NotFoundError
from src.supplies.domain.entities.trabajo_reporte_gasto import EjecucionReporteGasto, TrabajoReporteGasto
from src.supplies.domain.repositories.trabajo_reporte_gasto_repository import TrabajoReporteGastoRepository


@dataclass(frozen=True)
class EstadoTrabajoReporte:
    trabajo: TrabajoReporteGasto
    ultima_ejecucion: Optional[EjecucionReporteGasto]


class ConsultarEstadoTrabajoReporteUseCase:
    def __init__(self, trabajo_repo: TrabajoReporteGastoRepository) -> None:
        self.trabajo_repo = trabajo_repo

    def execute(self, id_cola: int) -> EstadoTrabajoReporte:
        trabajo = self.trabajo_repo.obtener(id_cola)
        if trabajo is None:
            raise NotFoundError(
                code="TRABAJO_NO_ENCONTRADO",
                message=f"El trabajo de generación de reporte {id_cola} no existe.",
                field="id_cola",
            )
        ultima_ejecucion = self.trabajo_repo.obtener_ultima_ejecucion(id_cola)
        return EstadoTrabajoReporte(trabajo=trabajo, ultima_ejecucion=ultima_ejecucion)

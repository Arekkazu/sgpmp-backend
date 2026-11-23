# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
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
    """Trabajo asíncrono del reporte de gastos con su última ejecución."""
    trabajo: TrabajoReporteGasto
    ultima_ejecucion: Optional[EjecucionReporteGasto]


class ConsultarEstadoTrabajoReporteUseCase:
    """Consulta el estado de un trabajo del reporte de gastos."""
    def __init__(self, trabajo_repo: TrabajoReporteGastoRepository) -> None:
        self.trabajo_repo = trabajo_repo

    def execute(self, id_cola: int) -> EstadoTrabajoReporte:
        """Devuelve el estado del trabajo.

        Raises:
            NotFoundError: Si el trabajo no existe.
        """
        trabajo = self.trabajo_repo.obtener(id_cola)
        if trabajo is None:
            raise NotFoundError(
                code="TRABAJO_NO_ENCONTRADO",
                message=f"El trabajo de generación de reporte {id_cola} no existe.",
                field="id_cola",
            )
        ultima_ejecucion = self.trabajo_repo.obtener_ultima_ejecucion(id_cola)
        return EstadoTrabajoReporte(trabajo=trabajo, ultima_ejecucion=ultima_ejecucion)

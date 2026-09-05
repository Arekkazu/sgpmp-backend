"""Caso de uso: consultar un reporte de gastos ya generado (RF-77).

Solo lectura. Usado para releer el snapshot persistido de un reporte
síncrono o el resultado de un trabajo async ya completado.
"""
from __future__ import annotations

from src.shared.errors import NotFoundError
from src.supplies.domain.entities.reporte_gasto import ReporteGasto
from src.supplies.domain.repositories.reporte_gasto_repository import ReporteGastoRepository


class ConsultarReporteGastosUseCase:
    def __init__(self, reporte_repo: ReporteGastoRepository) -> None:
        self.reporte_repo = reporte_repo

    def execute(self, id_reporte_gasto_acumulado: int) -> ReporteGasto:
        reporte = self.reporte_repo.obtener(id_reporte_gasto_acumulado)
        if reporte is None:
            raise NotFoundError(
                code="REPORTE_NO_ENCONTRADO",
                message=f"El reporte de gastos {id_reporte_gasto_acumulado} no existe.",
                field="id_reporte_gasto_acumulado",
            )
        return reporte

"""Caso de uso: listar el historial de reportes generados (RF-77, RNF de historial).

Solo lectura. Permite al usuario regenerar en pantalla cualquier reporte
previamente generado reutilizando sus parámetros guardados.
"""
from __future__ import annotations

from typing import Optional

from src.supplies.domain.entities.reporte_gasto import ReporteGasto
from src.supplies.domain.repositories.reporte_gasto_repository import ReporteGastoRepository


class ListarHistorialReportesUseCase:
    def __init__(self, reporte_repo: ReporteGastoRepository) -> None:
        self.reporte_repo = reporte_repo

    def execute(self, id_usuario: Optional[int], limite: int = 20) -> list[ReporteGasto]:
        return self.reporte_repo.listar_historial(id_usuario, limite)

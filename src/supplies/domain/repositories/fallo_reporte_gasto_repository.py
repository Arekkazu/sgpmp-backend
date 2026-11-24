# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de fallos persistentes del motor async de reportes de gastos (RF-77)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.supplies.domain.entities.trabajo_reporte_gasto import FalloReporteGasto


class FalloReporteGastoRepository(ABC):
    """Puerto de persistencia de fallos del reporte de gastos asíncrono."""
    @abstractmethod
    def registrar(self, fallo: FalloReporteGasto) -> FalloReporteGasto:
        """Registra el fallo."""
        raise NotImplementedError

    @abstractmethod
    def listar_no_resueltos(self) -> list[FalloReporteGasto]:
        """Lista los fallos sin resolver."""
        raise NotImplementedError

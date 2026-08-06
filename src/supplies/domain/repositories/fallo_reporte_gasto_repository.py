"""Puerto de fallos persistentes del motor async de reportes de gastos (RF-77)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.supplies.domain.entities.trabajo_reporte_gasto import FalloReporteGasto


class FalloReporteGastoRepository(ABC):
    @abstractmethod
    def registrar(self, fallo: FalloReporteGasto) -> FalloReporteGasto:
        raise NotImplementedError

    @abstractmethod
    def listar_no_resueltos(self) -> list[FalloReporteGasto]:
        raise NotImplementedError

"""Puerto de persistencia del snapshot de reportes de gastos (RF-77)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.supplies.domain.entities.reporte_gasto import ReporteGasto


class ReporteGastoRepository(ABC):
    @abstractmethod
    def guardar(self, reporte: ReporteGasto) -> ReporteGasto:
        """Persiste el snapshot del reporte en ``reporte_gastos_acumulados``."""
        raise NotImplementedError

    @abstractmethod
    def obtener(self, id_reporte_gasto_acumulado: int) -> Optional[ReporteGasto]:
        raise NotImplementedError

    @abstractmethod
    def listar_historial(self, id_usuario: Optional[int], limite: int = 20) -> list[ReporteGasto]:
        """Historial de reportes generados (RNF de RF-77), más recientes primero."""
        raise NotImplementedError

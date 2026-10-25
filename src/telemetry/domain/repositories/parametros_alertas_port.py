# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-21 | Arekkazu | DEV-32 RF-57: umbrales de tormenta (E8) |
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional


class ParametrosAlertasPort(ABC):
    @abstractmethod
    def obtener_confianza_edge_ia(self) -> Decimal:
        """Umbral configurable de resolución de conflictos E12/E13 de RF-57."""

    @abstractmethod
    def obtener_umbrales_tormenta(self) -> Optional[tuple[int, int]]:
        """RF-57 E8: (alertas/min del sistema, alertas/min por unidad) que activan la
        tormenta, o ``None`` si no están configurados (sin agrupación)."""

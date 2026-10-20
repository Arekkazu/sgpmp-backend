from abc import ABC, abstractmethod
from decimal import Decimal


class ParametrosAlertasPort(ABC):
    @abstractmethod
    def obtener_confianza_edge_ia(self) -> Decimal:
        """Umbral configurable de resolución de conflictos E12/E13 de RF-57."""

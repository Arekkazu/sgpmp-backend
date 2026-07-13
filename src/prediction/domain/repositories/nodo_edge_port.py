from __future__ import annotations

from abc import ABC, abstractmethod


class NodoEdgePort(ABC):
    @abstractmethod
    def hay_nodos_activos(self, tipo_modelo: str) -> bool:
        """Devuelve True si hay al menos un nodo Edge activo para el tipo de modelo."""
        ...

from __future__ import annotations

from abc import ABC, abstractmethod


class VariableI3P1Port(ABC):
    @abstractmethod
    def obtener_ids_activos(self, ids: list[int]) -> list[int]:
        """Devuelve los ids que existen y están activos en el catálogo I3P-1."""
        ...

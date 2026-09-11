from __future__ import annotations

from abc import ABC, abstractmethod


class EspeciePort(ABC):
    @abstractmethod
    def especie_activa(self, especie_aplicable: str) -> bool:
        """Retorna True si especie_aplicable es 'TODAS' o un id_especie activo en M09."""
        ...

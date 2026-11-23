# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de consulta de especies."""
from __future__ import annotations

from abc import ABC, abstractmethod


class EspeciePort(ABC):
    """Puerto para verificar si una especie está activa."""
    @abstractmethod
    def especie_activa(self, especie_aplicable: str) -> bool:
        """Retorna True si especie_aplicable es 'TODAS' o un id_especie activo en M09."""
        ...

# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-162-G68 RF-57: rango absoluto y criticidad de la variable (FALLO_AMBIENTAL) |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de rango físico y criticidad de variables para alertas."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class RangoFisicoVariable:
    """Rango absoluto del sensor (no el operativo) y si la variable es crítica (RF-17)."""
    valor_fisico_min: Optional[Decimal]
    valor_fisico_max: Optional[Decimal]
    es_critica: bool


class VariableAlertaPort(ABC):
    """Puerto para obtener el rango físico de una variable del catálogo."""
    @abstractmethod
    def obtener_rango_fisico(self, tipo_variable: str) -> Optional[RangoFisicoVariable]:
        """``None`` si la variable no está en el catálogo de M09."""

"""Read-model: variable ambiental del catálogo predefinido (modulo9.variables_ambientales)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class VariableAmbiental:
    id_variable_ambiental: int
    nombre: str
    unidad: str
    valor_fisico_min: Decimal
    valor_fisico_max: Decimal
    es_activo: bool

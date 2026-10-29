# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-25 RF-17: es_critica y _snapshot (RFC-016) |
"""Read-model: variable ambiental del catálogo predefinido (modulo9.variables_ambientales)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class VariableAmbiental:
    """Variable ambiental del catálogo con su unidad y rango físico posible."""
    id_variable_ambiental: int
    nombre: str
    unidad: str
    valor_fisico_min: Decimal
    valor_fisico_max: Decimal
    es_activo: bool
    # RFC-016 B.7: editable solo por el Administrador.
    es_critica: bool = False

    def _snapshot(self) -> dict:
        return {"id_variable_ambiental": self.id_variable_ambiental, "nombre": self.nombre, "es_critica": self.es_critica}

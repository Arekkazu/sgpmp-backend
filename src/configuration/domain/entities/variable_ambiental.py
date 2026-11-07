# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-25 RF-17: es_critica y _snapshot (RFC-016) |
# | 2026-10-31 | Arekkazu | USAB-M03-M04 M4-02 RF-64: catálogo de variables con código de telemetría |
"""Read-model: variable ambiental del catálogo predefinido (modulo9.variables_ambientales)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


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
    # M4-02: código de telemetría; con él M04 sabe qué variables admite una patología (RF-64).
    codigo_telemetria: Optional[str] = None

    def _snapshot(self) -> dict:
        return {"id_variable_ambiental": self.id_variable_ambiental, "nombre": self.nombre, "es_critica": self.es_critica}

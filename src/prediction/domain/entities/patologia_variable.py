# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-25 | Arekkazu | USAB-M04 M4-02 RF-64: nombre y unidad de variables y nombre de la especie (read-model) |
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


@dataclass
class PatologiaVariable:
    id_variable_ambiental: int
    peso_evidencia: Decimal = field(default_factory=lambda: Decimal("1.000"))
    es_variable_critica: bool = False
    id_patologia_variable: Optional[int] = None
    # M4-02 (read-model, del catálogo I3P-1): antes el front mostraba "Variable 13".
    nombre: Optional[str] = None
    unidad: Optional[str] = None

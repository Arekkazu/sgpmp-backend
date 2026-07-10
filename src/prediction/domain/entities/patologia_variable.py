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

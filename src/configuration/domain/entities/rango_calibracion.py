"""Entidad de dominio ``RangoCalibracion`` — rango de seguridad por tipo de sensor (RF-24).

Cada tipo de sensor (``categoria``) define el rango [min, max] admisible para el
valor de calibración. Un valor fuera de ese rango se rechaza (offset absurdo,
ej. temperatura 500 °C o pH −5).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class RangoCalibracion:
    categoria: str
    valor_min: Decimal
    valor_max: Decimal

    def verificar(self, valor: Decimal) -> Optional[dict]:
        """Devuelve la violación como dict (min/max/valor) o None si el valor cabe."""
        if not (self.valor_min <= valor <= self.valor_max):
            return {"min": self.valor_min, "max": self.valor_max, "valor": valor}
        return None

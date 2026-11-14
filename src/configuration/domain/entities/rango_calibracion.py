# | Fecha      | Nombre   | Que se hizo                                                  |
# |------------|----------|--------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M03-137-G09 RF-24: límite propio del offset (admite negativos) |
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
    """Rango [min, max] admisible del valor de calibración para un tipo de sensor
    (RF-24).
    """
    categoria: str
    valor_min: Decimal
    valor_max: Decimal

    def verificar(self, valor: Decimal) -> Optional[dict]:
        """Devuelve la violación como dict (min/max/valor) o None si el valor cabe."""
        if not (self.valor_min <= valor <= self.valor_max):
            return {"min": self.valor_min, "max": self.valor_max, "valor": valor}
        return None

    def verificar_offset(self, offset: Decimal) -> Optional[dict]:
        """El offset es una corrección, no una lectura: puede ser negativo (INC-M03-137-G09).

        ponytail: límite = ± la amplitud del rango de medición del tipo de sensor; si se
        necesita un tope por tipo, agregar la columna al catálogo de rangos.
        """
        amplitud = self.valor_max - self.valor_min
        if abs(offset) > amplitud:
            return {"min": -amplitud, "max": amplitud, "valor": offset}
        return None

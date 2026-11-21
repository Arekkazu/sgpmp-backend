# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-66 POBLACIONAL: conteo de la cámara contra el inventario del lote |
"""Conteo de la cámara frente al inventario del área (``cantidad_actual`` de sus lotes POBLACIONAL).

La cámara nunca cuenta exacto (oclusiones, encuadre, detector pequeño), así que solo se avisa si las
últimas ``VENTANAS`` ventanas aptas se alejan del inventario más que ``TOLERANCIA``. Solo es un aviso:
el inventario lo corrige el usuario en M02. Valores provisionales (DEV), medidos con el video de prueba:
en la granja la cámara ve 11 de unos 15 cerdos (27 % menos).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

TOLERANCIA = Decimal("0.35")
VENTANAS = 3


def hay_discrepancia(conteos_recientes: list[int], cantidad_registrada: Optional[int]) -> bool:
    """``conteos_recientes`` del más nuevo al más viejo; False si aún no hay suficientes ventanas."""
    if cantidad_registrada is None or len(conteos_recientes) < VENTANAS:
        return False
    margen = TOLERANCIA * max(cantidad_registrada, 1)
    return all(abs(c - cantidad_registrada) > margen for c in conteos_recientes[:VENTANAS])

# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-78: corrección aditiva (R12/RNF-09)    |
"""DTO de entrada para una CORRECCION del ledger de RF-78.

La corrección es un ajuste que SUMA al acumulado (R12, CA-8): su costo es
``cantidad × precio_unitario`` y puede ser negativo (RNF-09) usando un precio
negativo; la cantidad siempre es > 0. ``id_registro_original`` va en la ruta
(E7: si no existe → 422).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import Field

from src.shared.base_dto import BaseDTO


class RegistrarCorreccionSuministroDTO(BaseDTO):
    id_idempotencia: UUID
    cantidad: Decimal = Field(description="Cantidad del ajuste (> 0).")
    precio_unitario: Decimal = Field(description="Precio unitario del ajuste; negativo si compensa (≠ 0).")
    justificacion_precio: Optional[str] = None
    motivo_correccion: str = Field(min_length=20, max_length=500)

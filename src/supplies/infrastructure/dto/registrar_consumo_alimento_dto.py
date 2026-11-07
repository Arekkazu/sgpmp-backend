# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-75: costo_unitario, E4 y observaciones |
"""DTO de entrada para registrar un consumo de alimento (RF-75).

El alimento se elige del catálogo ``modulo5.tipos_alimentos`` (su nombre es el
``tipo_alimento`` del registro); ``costo_unitario`` (COP/kg) es una entrada
obligatoria y ``costo_total = cantidad × costo_unitario`` lo calcula la BD
(RF-75 paso 8). Los errores de formato responden 400 (RF-75 paso 7, E4).
"""
from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from typing import Optional

from pydantic import Field, field_validator

from src.shared.base_dto import BaseDTO


class RegistrarConsumoAlimentoDTO(BaseDTO):
    """Campos requeridos para registrar un consumo de alimento."""

    id_activo_biologico: int = Field(gt=0)
    id_tipo_alimento: int = Field(gt=0)
    fecha_consumo: date
    hora_suministro: Optional[time] = None
    cantidad_alimento: Decimal = Field(description="Cantidad total suministrada en kg (> 0).")
    costo_unitario: Decimal = Field(description="Costo del alimento en COP por kilogramo (> 0).")
    observaciones: Optional[str] = Field(default=None, max_length=255)

    @field_validator("cantidad_alimento")
    @classmethod
    def validar_cantidad(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError(f"La cantidad de alimento debe ser mayor a cero kilogramos. Valor ingresado: {v} kg.")
        return v

    @field_validator("costo_unitario")
    @classmethod
    def validar_costo(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError(f"El costo unitario del alimento debe ser mayor a cero. Valor ingresado: {v} COP/kg.")
        return v

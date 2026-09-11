"""DTO de entrada para registrar un consumo de alimento (RF-75).

Nota: ``costo_unitario`` NO se recibe. El costo es autoritativo desde el
catálogo ``modulo5.tipos_alimentos`` (el trigger ``fn_trg_calcular_costo_total_consumo``
calcula ``costo_total`` con el precio del catálogo activo). ``observaciones`` se
limita a 60 caracteres por el tamaño de la columna ``observacion``.
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
    cantidad_alimento: Decimal = Field(gt=0, description="Cantidad total suministrada en kg (> 0).")
    observaciones: Optional[str] = None

    @field_validator("observaciones")
    @classmethod
    def validar_observaciones(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 60:
            raise ValueError("Las observaciones no pueden superar los 60 caracteres.")
        return v

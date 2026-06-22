"""DTO de entrada para registrar una calibración de sensor (POST /{id}/calibrar RF-24)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import field_validator

from src.shared.base_dto import BaseDTO


class RegistrarCalibracionDTO(BaseDTO):
    id_dispositivo_iot: int
    id_infraestructura: int
    valor_referencia: Decimal
    fecha_calibracion: datetime
    observaciones: Optional[str] = None

    @field_validator("valor_referencia")
    @classmethod
    def validar_valor(cls, v: Decimal) -> Decimal:
        if v <= Decimal("0"):
            raise ValueError(f"El valor de referencia debe ser positivo. Valor recibido: {v}.")
        return v

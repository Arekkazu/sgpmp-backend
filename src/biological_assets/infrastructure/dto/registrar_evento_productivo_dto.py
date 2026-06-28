from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import field_validator

from src.shared.base_dto import BaseDTO


class RegistrarEventoProductivoDTO(BaseDTO):
    cantidad: Decimal
    id_metrica_produccion: int
    id_ciclo_productivo: int
    condiciones: Optional[str] = None
    fecha: Optional[datetime] = None
    descripcion: Optional[str] = None

    @field_validator('cantidad')
    @classmethod
    def cantidad_positiva(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError('La cantidad debe ser mayor a cero.')
        return v

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import field_validator

from src.shared.base_dto import BaseDTO


class RegistrarEventoProductivoDTO(BaseDTO):
    tipo_producto: str
    cantidad_producida: Decimal
    unidad_medida: str
    fecha_evento: date
    condiciones_produccion: Optional[str] = None
    observaciones: Optional[str] = None

    @field_validator('tipo_producto')
    @classmethod
    def tipo_no_vacio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('El tipo de producto no puede estar vacío.')
        return v.upper()

    @field_validator('unidad_medida')
    @classmethod
    def unidad_no_vacia(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('La unidad de medida no puede estar vacía.')
        return v

    @field_validator('cantidad_producida')
    @classmethod
    def cantidad_positiva(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError('La cantidad producida debe ser un valor numérico positivo mayor a cero.')
        return v

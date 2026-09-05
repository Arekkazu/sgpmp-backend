from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import field_validator

from src.shared.base_dto import BaseDTO

_TIPOS_BAJA = {'muerte', 'venta', 'sacrificio', 'perdida', 'descarte_sanitario'}


class RegistrarEventoBajaDTO(BaseDTO):
    tipo_baja: str
    fecha_baja: date
    motivo_baja: str
    cantidad_afectada: Optional[int] = None  # solo LOTE baja parcial; None = baja total del lote

    @field_validator('tipo_baja')
    @classmethod
    def tipo_valido(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in _TIPOS_BAJA:
            raise ValueError(f"El tipo de baja debe ser uno de: {', '.join(sorted(_TIPOS_BAJA))}.")
        return v

    @field_validator('motivo_baja')
    @classmethod
    def motivo_no_vacio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('El motivo de baja no puede estar vacío.')
        return v

    @field_validator('cantidad_afectada')
    @classmethod
    def cantidad_positiva(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError('La cantidad afectada debe ser un entero positivo.')
        return v

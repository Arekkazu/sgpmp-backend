from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import field_validator

from src.shared.base_dto import BaseDTO

_TIPOS_BAJA = {'muerte', 'venta', 'sacrificio', 'perdida', 'descarte_sanitario'}


class RegistrarEventoBajaDTO(BaseDTO):
    cantidad_afectada: int
    tipo: str
    detalles: Optional[str] = None
    fecha: Optional[datetime] = None
    descripcion: Optional[str] = None

    @field_validator('cantidad_afectada')
    @classmethod
    def cantidad_positiva(cls, v: int) -> int:
        if v <= 0:
            raise ValueError('La cantidad afectada debe ser un entero positivo.')
        return v

    @field_validator('tipo')
    @classmethod
    def tipo_valido(cls, v: str) -> str:
        if v not in _TIPOS_BAJA:
            raise ValueError(f"El tipo de baja debe ser uno de: {', '.join(sorted(_TIPOS_BAJA))}.")
        return v

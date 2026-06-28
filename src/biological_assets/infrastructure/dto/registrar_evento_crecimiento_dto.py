from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import field_validator

from src.shared.base_dto import BaseDTO

_UNIDADES_VALIDAS = {'kg', 'gr', 'lb', 'cm', 'm', 'kg/m2'}


class RegistrarEventoCrecimientoDTO(BaseDTO):
    tipo_medicion: str
    valor_medicion: Decimal
    unidad_medida: str
    tipo_agregacion: str
    frecuencia: str
    fecha: Optional[datetime] = None
    descripcion: Optional[str] = None

    @field_validator('valor_medicion')
    @classmethod
    def valor_positivo(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError('El valor de medición debe ser mayor a cero.')
        return v

    @field_validator('unidad_medida')
    @classmethod
    def unidad_valida(cls, v: str) -> str:
        if v not in _UNIDADES_VALIDAS:
            raise ValueError(f"La unidad de medida debe ser una de: {', '.join(sorted(_UNIDADES_VALIDAS))}.")
        return v

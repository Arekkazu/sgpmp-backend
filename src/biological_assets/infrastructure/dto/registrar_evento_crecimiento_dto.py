from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import field_validator, model_validator

from src.shared.base_dto import BaseDTO

_TIPOS_MEDICION = {'PESO', 'TALLA', 'BIOMASA'}

_UNIDADES_VALIDAS = {'kg', 'gr', 'lb', 'cm', 'm', 'kg/m2'}

_UNIDADES_POR_TIPO: dict[str, set[str]] = {
    'PESO':    {'kg', 'gr', 'lb'},
    'TALLA':   {'cm', 'm'},
    'BIOMASA': {'kg/m2'},
}


class RegistrarEventoCrecimientoDTO(BaseDTO):
    tipo_medicion: str
    valor_medicion: Decimal
    unidad_medida: str
    tipo_agregacion: Optional[str] = None
    frecuencia: Optional[str] = None
    nuevo_peso_promedio: Optional[Decimal] = None
    cantidad_medida: Optional[int] = None
    fecha: Optional[datetime] = None
    descripcion: Optional[str] = None

    @field_validator('tipo_medicion')
    @classmethod
    def tipo_valido(cls, v: str) -> str:
        if v not in _TIPOS_MEDICION:
            raise ValueError(f"El tipo de medición debe ser uno de: {', '.join(sorted(_TIPOS_MEDICION))}.")
        return v

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

    @field_validator('nuevo_peso_promedio')
    @classmethod
    def nuevo_peso_positivo(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v <= 0:
            raise ValueError('El nuevo peso promedio debe ser mayor a cero.')
        return v

    @field_validator('cantidad_medida')
    @classmethod
    def cantidad_medida_positiva(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError('La cantidad medida debe ser mayor a cero.')
        return v

    @model_validator(mode='after')
    def validar_unidad_por_tipo(self) -> RegistrarEventoCrecimientoDTO:
        tipo = self.tipo_medicion
        unidad = self.unidad_medida
        if tipo and unidad and tipo in _UNIDADES_POR_TIPO:
            permitidas = _UNIDADES_POR_TIPO[tipo]
            if unidad not in permitidas:
                raise ValueError(
                    f"La unidad de medida '{unidad}' no corresponde al tipo de medición '{tipo}'. "
                    f"Unidades permitidas para {tipo}: {', '.join(sorted(permitidas))}."
                )
        return self

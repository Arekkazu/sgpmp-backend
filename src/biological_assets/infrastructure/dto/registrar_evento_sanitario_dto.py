from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import field_validator, model_validator

from src.shared.base_dto import BaseDTO

_TIPOS_SANITARIO = {'VACUNACION', 'TRATAMIENTO', 'DIAGNOSTICO', 'CONTROL_PREVENTIVO'}


class RegistrarEventoSanitarioDTO(BaseDTO):
    tipo: str
    diagnostico: Optional[str] = None
    medicamento: Optional[str] = None
    dosis: Optional[Decimal] = None
    unidad_dosis: Optional[str] = None
    frecuencia: Optional[int] = None
    duracion: Optional[int] = None
    observaciones: Optional[str] = None
    fecha: Optional[datetime] = None
    descripcion: Optional[str] = None

    @field_validator('tipo')
    @classmethod
    def tipo_valido(cls, v: str) -> str:
        if v not in _TIPOS_SANITARIO:
            raise ValueError(f"El tipo sanitario debe ser uno de: {', '.join(sorted(_TIPOS_SANITARIO))}.")
        return v

    @model_validator(mode='after')
    def validar_campos_por_tipo(self) -> RegistrarEventoSanitarioDTO:
        tipo = self.tipo
        if tipo == 'VACUNACION':
            if self.medicamento is None or self.dosis is None:
                raise ValueError('VACUNACION requiere medicamento y dosis.')
        elif tipo == 'TRATAMIENTO':
            if any(v is None for v in [self.medicamento, self.dosis, self.frecuencia, self.duracion]):
                raise ValueError('TRATAMIENTO requiere medicamento, dosis, frecuencia y duracion.')
        elif tipo == 'DIAGNOSTICO':
            if self.diagnostico is None:
                raise ValueError('DIAGNOSTICO requiere el campo diagnostico.')
        elif tipo == 'CONTROL_PREVENTIVO':
            if self.observaciones is None:
                raise ValueError('CONTROL_PREVENTIVO requiere el campo observaciones.')
        return self

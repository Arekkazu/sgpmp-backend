from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import field_validator

from src.shared.base_dto import BaseDTO

_MOTIVOS_VALIDOS = {'venta', 'sacrificio', 'muerte', 'finalizacion_lote', 'otro'}


class CerrarCicloDTO(BaseDTO):
    fecha_cierre: date
    motivo_cierre: str
    descripcion_cierre: Optional[str] = None

    @field_validator('fecha_cierre')
    @classmethod
    def fecha_no_futura(cls, v: date) -> date:
        if v > date.today():
            raise ValueError('La fecha de cierre no puede ser futura.')
        return v

    @field_validator('motivo_cierre')
    @classmethod
    def motivo_no_vacio(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Debe indicar un motivo de cierre.')
        return v.strip()

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import field_validator, model_validator

from src.shared.base_dto import BaseDTO

_TIPOS_DATO = {'eventos', 'fases', 'estado', 'metricas', 'todos'}


class DatosConsolidadosDTO(BaseDTO):
    tipo_dato: str = 'todos'
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    pagina: int = 1
    page_size: int = 20

    @field_validator('tipo_dato', mode='before')
    @classmethod
    def validar_tipo_dato(cls, v: object) -> str:
        v_str = str(v).strip().lower()
        if v_str not in _TIPOS_DATO:
            raise ValueError(
                f'Tipo de dato inválido. Valores permitidos: {", ".join(sorted(_TIPOS_DATO))}.'
            )
        return v_str

    @field_validator('pagina', mode='before')
    @classmethod
    def validar_pagina(cls, v: object) -> int:
        val = int(v)
        if val < 1:
            raise ValueError('La página debe ser mayor o igual a 1.')
        return val

    @field_validator('page_size', mode='before')
    @classmethod
    def validar_page_size(cls, v: object) -> int:
        val = int(v)
        if val < 1 or val > 100:
            raise ValueError('El tamaño de página debe estar entre 1 y 100.')
        return val

    @model_validator(mode='after')
    def validar_rango_fechas(self) -> DatosConsolidadosDTO:
        if self.fecha_inicio and self.fecha_fin and self.fecha_inicio > self.fecha_fin:
            raise ValueError(
                f'La fecha de inicio ({self.fecha_inicio}) no puede ser posterior '
                f'a la fecha de fin ({self.fecha_fin}).'
            )
        return self

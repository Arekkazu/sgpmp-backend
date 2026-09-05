from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import field_validator, model_validator

from src.shared.base_dto import BaseDTO

_TIPOS_VALIDOS = {'CRECIMIENTO', 'PRODUCCION', 'SANITARIO', 'EFICIENCIA', 'TODOS'}


class ConsultarIndicadoresDTO(BaseDTO):
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    tipo_indicador: str = 'TODOS'

    @field_validator('tipo_indicador', mode='before')
    @classmethod
    def validar_tipo(cls, v: object) -> str:
        v_str = str(v).strip().upper()
        if v_str not in _TIPOS_VALIDOS:
            raise ValueError(
                f'Tipo de indicador inválido. Valores permitidos: {", ".join(sorted(_TIPOS_VALIDOS))}.'
            )
        return v_str

    @model_validator(mode='after')
    def validar_rango_fechas(self) -> ConsultarIndicadoresDTO:
        if self.fecha_inicio and self.fecha_fin and self.fecha_inicio > self.fecha_fin:
            raise ValueError(
                f'La fecha de inicio ({self.fecha_inicio}) no puede ser posterior '
                f'a la fecha de fin ({self.fecha_fin}).'
            )
        return self

# | Fecha      | Nombre  | Que se hizo                                         |
# |------------|---------|-----------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-30 RF-57: deriva CERRADA a validacion de dominio  |
from __future__ import annotations

from typing import Optional

from pydantic import Field, field_validator

from src.shared.base_dto import BaseDTO


class ActualizarEstadoAlertaDTO(BaseDTO):
    nuevo_estado: str = Field(..., min_length=2, max_length=30)
    motivo: Optional[str] = Field(default=None, max_length=500)

    @field_validator('nuevo_estado')
    @classmethod
    def validar_estado(cls, v: str) -> str:
        # CERRADA se reconoce como solicitud, pero no pertenece al catálogo:
        # el dominio la rechaza con TRANSICION_INVALIDA (422).
        validos = {'EN_ATENCION', 'RESUELTA', 'DESCARTADA', 'VENCIDA', 'CERRADA'}
        v = v.upper()
        if v not in validos:
            raise ValueError(f"nuevo_estado debe ser uno de: {', '.join(validos)}")
        return v

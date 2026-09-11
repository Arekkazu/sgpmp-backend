from __future__ import annotations

from typing import Optional

from pydantic import Field, field_validator

from src.shared.base_dto import BaseDTO


class AplicarMantenimientoDTO(BaseDTO):
    """Transición manual de mantenimiento de un dispositivo IoT (RF-60 CA-7/CA-8).

    Solo admite los dos estados de la transición manual bidireccional; el resto
    de estados son gestionados por el job periódico, no por acción de usuario.
    """

    nuevo_estado: str = Field(..., min_length=2, max_length=30)
    motivo: Optional[str] = Field(default=None, max_length=500)

    @field_validator('nuevo_estado')
    @classmethod
    def validar_estado(cls, v: str) -> str:
        v = v.upper()
        if v not in {'EN_MANTENIMIENTO', 'ACTIVO'}:
            raise ValueError("nuevo_estado debe ser 'EN_MANTENIMIENTO' o 'ACTIVO'")
        return v

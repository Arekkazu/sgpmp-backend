# | Fecha      | Nombre  | Que se hizo                                         |
# |------------|---------|-----------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-30 RF-57: deriva CERRADA a validacion de dominio  |
# | 2026-10-28 | destroyerban | INC-M03-172-G79 RF-57 CA-11: estado no catalogado (FINALIZADA, vacío, null) → 422 TRANSICION_INVALIDA |
from __future__ import annotations

from typing import Optional

from pydantic import Field, field_validator

from src.shared.base_dto import BaseDTO


class ActualizarEstadoAlertaDTO(BaseDTO):
    # CA-11 (RFC-008): un estado no catalogado —CERRADA, FINALIZADA, vacío o null— no es un error de
    # forma sino una transición inválida; lo rechaza el caso de uso con 422 TRANSICION_INVALIDA.
    # El campo sigue siendo obligatorio y de texto: omitirlo o mandar otro tipo es 400 VAL_ENTRADA.
    nuevo_estado: Optional[str] = Field(..., max_length=50)
    motivo: Optional[str] = Field(default=None, max_length=500)

    @field_validator('nuevo_estado')
    @classmethod
    def normalizar_estado(cls, v: Optional[str]) -> Optional[str]:
        return v.upper() if v is not None else None

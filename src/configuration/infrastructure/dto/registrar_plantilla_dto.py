"""DTO de entrada para crear una nueva plantilla de configuración (RF-31)."""
from __future__ import annotations

from typing import Any

from pydantic import field_validator

from src.configuration.domain.esquema_plantilla import validar_snapshot
from src.shared.base_dto import BaseDTO


class RegistrarPlantillaDTO(BaseDTO):
    """Campos requeridos para crear una plantilla."""

    template_name: str
    id_especie: int
    params_snapshot: dict[str, Any]

    @field_validator('template_name')
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3 or len(v) > 50:
            raise ValueError('El nombre debe tener entre 3 y 50 caracteres.')
        return v

    @field_validator('params_snapshot')
    @classmethod
    def validar_estructura_snapshot(cls, v: dict) -> dict:
        """Rechaza el snapshot que no cumple el esquema vigente (RF-31, FA 400).

        El detalle va completo en el mensaje porque el RF exige que el error
        nombre los parámetros inválidos, no solo que la validación falló.
        """
        errores = validar_snapshot(v)
        if errores:
            raise ValueError(' '.join(errores))
        return v

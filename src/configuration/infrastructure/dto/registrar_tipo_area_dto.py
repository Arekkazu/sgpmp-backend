"""DTO de entrada para registrar un tipo de área en el catálogo (RF-20)."""
from __future__ import annotations

from pydantic import field_validator

from src.shared.base_dto import BaseDTO
from src.shared.regex import NOMBRE


class RegistrarTipoAreaDTO(BaseDTO):
    """Campo requerido para registrar un tipo de área en el catálogo."""

    nombre: str

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        if len(v) < 3 or len(v) > 30:
            raise ValueError("El nombre debe tener entre 3 y 30 caracteres.")
        if not NOMBRE.match(v):
            raise ValueError(
                "El nombre solo puede contener letras y espacios, sin símbolos ni números."
            )
        return v

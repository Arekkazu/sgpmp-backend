"""DTO de entrada para el registro de una nueva especie productiva (Flujo A — RF-15)."""
from typing import Optional

from pydantic import field_validator

from src.shared.base_dto import BaseDTO
from src.shared.regex import NOMBRE


class RegistrarEspecieDTO(BaseDTO):
    """Campos requeridos para registrar una especie en el catálogo."""

    nombre: str
    descripcion: Optional[str] = None

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        if len(v) < 3 or len(v) > 50:
            raise ValueError("El nombre debe tener entre 3 y 50 caracteres.")
        if not NOMBRE.match(v):
            raise ValueError(
                "El nombre solo puede contener letras y espacios, sin símbolos ni números."
            )
        return v

    @field_validator("descripcion")
    @classmethod
    def validar_descripcion(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 255:
            raise ValueError("La descripción no puede superar los 255 caracteres.")
        return v

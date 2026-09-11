"""DTO de entrada para la edición de una especie productiva (Flujo B — RF-15).

Incluye ``fecha_actualizacion`` como mecanismo de concurrencia optimista:
el cliente envía el timestamp que obtuvo al leer la especie; si difiere del
valor actual en BD, el use case rechaza la operación con 409.
"""
from datetime import datetime
from typing import Optional

from pydantic import field_validator

from src.shared.base_dto import BaseDTO
from src.shared.regex import NOMBRE


class EditarEspecieDTO(BaseDTO):
    """Campos editables de una especie y versión de concurrencia."""

    nombre: str
    descripcion: Optional[str] = None
    fecha_actualizacion: datetime

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

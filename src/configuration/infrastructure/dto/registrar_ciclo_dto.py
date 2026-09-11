"""DTO de entrada para registrar una etapa del ciclo productivo (Flujo A — RF-16)."""
from typing import Optional
import re

from pydantic import field_validator

from src.shared.base_dto import BaseDTO

_NOMBRE_ETAPA = re.compile(r"^[A-Za-zÁÉÍÓÚáéíóúÑñ][A-Za-zÁÉÍÓÚáéíóúÑñ0-9 \-()]*$")


class RegistrarCicloDTO(BaseDTO):
    id_especie: int
    nombre: str
    descripcion: Optional[str] = None
    duracion_dias: int

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3 or len(v) > 50:
            raise ValueError("El nombre de la etapa debe tener entre 3 y 50 caracteres.")
        if not _NOMBRE_ETAPA.match(v):
            raise ValueError(
                "El nombre de la etapa solo puede contener letras, números, espacios, guiones y paréntesis."
            )
        return v

    @field_validator("descripcion")
    @classmethod
    def validar_descripcion(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 255:
            raise ValueError("La descripción no puede superar los 255 caracteres.")
        return v

    @field_validator("duracion_dias")
    @classmethod
    def validar_duracion(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(
                f"La duración estimada debe ser un número entero positivo mayor a 0. Valor recibido: {v}."
            )
        return v

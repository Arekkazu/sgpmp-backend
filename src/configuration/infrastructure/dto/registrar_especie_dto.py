# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-19 RF-15: esperanza_vida_dias opcional, > 0 (RFC-014) |
"""DTO de entrada para el registro de una nueva especie productiva (Flujo A — RF-15)."""
from decimal import Decimal
from typing import Optional

from pydantic import field_validator

from src.shared.base_dto import BaseDTO
from src.shared.tipo_modelo import GrupoManejo
from src.shared.regex import NOMBRE


class RegistrarEspecieDTO(BaseDTO):
    """Campos requeridos para registrar una especie en el catálogo."""

    nombre: str
    descripcion: Optional[str] = None
    densidad_maxima_por_especie: Optional[Decimal] = None
    # RFC-014: opcional, en días (> 0).
    esperanza_vida_dias: Optional[int] = None
    # RF-15 v1.1: obligatorio; de él sale el modelo que RF-20 exige a las áreas.
    grupo_manejo: GrupoManejo

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

    @field_validator("densidad_maxima_por_especie")
    @classmethod
    def validar_densidad_maxima(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v <= 0:
            raise ValueError("La densidad máxima por especie debe ser mayor a cero.")
        return v

    @field_validator("esperanza_vida_dias")
    @classmethod
    def validar_esperanza_vida(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("La esperanza de vida debe ser un número entero de días mayor a cero.")
        return v

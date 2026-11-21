# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-19 RF-15: esperanza_vida_dias opcional, > 0 (RFC-014) |
# | 2026-10-20 | Arekkazu | DEV-21 RF-15: densidad_poblacional_max (alias del nombre anterior), > 0 y máximo 2 decimales |
"""DTO de entrada para el registro de una nueva especie productiva (Flujo A — RF-15)."""
from decimal import Decimal
from typing import Optional

from pydantic import field_validator, model_validator

from src.shared.base_dto import BaseDTO
from src.configuration.infrastructure.dto.alias_densidad_poblacional import (
    campo_densidad,
    validar_alias_densidad,
    validar_densidad,
)
from src.shared.tipo_modelo import GrupoManejo
from src.shared.regex import NOMBRE


class RegistrarEspecieDTO(BaseDTO):
    """Campos requeridos para registrar una especie en el catálogo."""

    nombre: str
    descripcion: Optional[str] = None
    # RFC-012: ind/m², entra como densidad_poblacional_max (o el nombre anterior).
    densidad_maxima_por_especie: Optional[Decimal] = campo_densidad()
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

    @model_validator(mode="before")
    @classmethod
    def comprobar_alias_densidad(cls, datos):
        return validar_alias_densidad(datos)

    @field_validator("densidad_maxima_por_especie")
    @classmethod
    def validar_densidad_maxima(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        return validar_densidad(v)

    @field_validator("esperanza_vida_dias")
    @classmethod
    def validar_esperanza_vida(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("La esperanza de vida debe ser un número entero de días mayor a cero.")
        return v

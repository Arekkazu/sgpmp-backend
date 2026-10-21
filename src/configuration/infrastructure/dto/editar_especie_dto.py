# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-19 RF-15: esperanza_vida_dias opcional, > 0 (RFC-014) |
"""DTO de entrada para la edición de una especie productiva (Flujo B — RF-15).

Incluye ``fecha_actualizacion`` como mecanismo de concurrencia optimista:
el cliente envía el timestamp que obtuvo al leer la especie; si difiere del
valor actual en BD, el use case rechaza la operación con 412.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import field_validator

from src.shared.base_dto import BaseDTO
from src.shared.tipo_modelo import GrupoManejo
from src.shared.regex import NOMBRE


class EditarEspecieDTO(BaseDTO):
    """Campos editables de una especie y versión de concurrencia."""

    nombre: str
    descripcion: Optional[str] = None
    densidad_maxima_por_especie: Optional[Decimal] = None
    # RFC-014: opcional, en días (> 0).
    esperanza_vida_dias: Optional[int] = None
    # RF-15 v1.1: omitido conserva el actual; no se puede vaciar (es obligatorio).
    grupo_manejo: Optional[GrupoManejo] = None
    # Null en una especie que nunca se editó: el registro no la llena (#231).
    fecha_actualizacion: Optional[datetime] = None

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

    @field_validator("grupo_manejo")
    @classmethod
    def validar_grupo_manejo(cls, v: Optional[str]) -> str:
        if v is None:
            raise ValueError("El grupo de manejo es obligatorio.")
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

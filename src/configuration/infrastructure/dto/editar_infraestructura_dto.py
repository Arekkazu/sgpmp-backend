"""DTO de entrada para editar un área productiva (PATCH RF-20).

Incluye ``fecha_actualizacion`` para concurrencia optimista (FA-14).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import field_validator

from src.configuration.infrastructure.models.enums_models import EnumTipoInfraestructura
from src.shared.base_dto import BaseDTO


class EditarInfraestructuraDTO(BaseDTO):
    nombre_infraestructura: str
    tipo_area: EnumTipoInfraestructura
    superficie: Decimal
    descripcion_infraestructura: Optional[str] = None
    fecha_actualizacion: Optional[datetime] = None

    @field_validator("nombre_infraestructura")
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El nombre del área productiva es obligatorio.")
        if len(v.strip()) > 50:
            raise ValueError("El nombre no puede superar los 50 caracteres.")
        return v

    @field_validator("superficie")
    @classmethod
    def validar_superficie(cls, v: Decimal) -> Decimal:
        if v <= Decimal("0"):
            raise ValueError(f"La superficie debe ser mayor a cero. Valor recibido: {v}.")
        return v

    @field_validator("descripcion_infraestructura")
    @classmethod
    def validar_descripcion(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 100:
            raise ValueError("La descripción no puede superar los 100 caracteres.")
        return v

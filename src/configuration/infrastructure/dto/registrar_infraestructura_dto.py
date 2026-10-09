"""DTO de entrada para registrar un área productiva (POST RF-20)."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from pydantic import field_validator

from src.shared.base_dto import BaseDTO
from src.shared.tipo_modelo import TipoModelo


class RegistrarInfraestructuraDTO(BaseDTO):
    """Área productiva nueva; ``tipo_area`` debe existir en el catálogo y ``superficie``
    va en m².
    """
    nombre_infraestructura: str
    tipo_area: str
    superficie: Decimal
    finca_id: int
    descripcion_infraestructura: Optional[str] = None
    # RF-20 v1.1 (RFC-009): especie obligatoria; el modelo de IA es opcional y
    # el use case valida su coherencia con la especie (422).
    especie_id: int
    tipo_modelo_asignado: Optional[TipoModelo] = None

    @field_validator("nombre_infraestructura")
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El nombre del área productiva es obligatorio.")
        if len(v.strip()) > 50:
            raise ValueError("El nombre no puede superar los 50 caracteres.")
        return v

    @field_validator("tipo_area")
    @classmethod
    def validar_tipo_area(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El tipo de área es obligatorio.")
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

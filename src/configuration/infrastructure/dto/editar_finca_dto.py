"""DTO de entrada para editar una finca (PATCH RF-19).

Incluye ``fecha_actualizacion`` como token de concurrencia optimista.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import field_validator

from src.configuration.infrastructure.dto.registrar_finca_dto import UbicacionFincaDTO
from src.shared.base_dto import BaseDTO


class EditarFincaDTO(BaseDTO):
    nombre: str
    ubicacion: UbicacionFincaDTO
    tamano_h: Decimal
    fecha_actualizacion: datetime

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El nombre de la finca es obligatorio.")
        if len(v.strip()) > 55:
            raise ValueError("El nombre no puede superar los 55 caracteres.")
        return v

    @field_validator("tamano_h")
    @classmethod
    def validar_tamano(cls, v: Decimal) -> Decimal:
        if v <= Decimal("0"):
            raise ValueError(f"El tamaño debe ser mayor a cero. Valor recibido: {v}.")
        return v

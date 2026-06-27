"""DTO de entrada para registrar una finca (POST RF-19)."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional

from pydantic import field_validator, model_validator

from src.shared.base_dto import BaseDTO


class UbicacionFincaDTO(BaseDTO):
    departamento: str
    municipio: str
    vereda: str
    latitud: Decimal
    longitud: Decimal

    @field_validator("latitud")
    @classmethod
    def validar_latitud(cls, v: Decimal) -> Decimal:
        if v < Decimal("-90") or v > Decimal("90"):
            raise ValueError("La latitud debe estar entre -90 y 90.")
        return v

    @field_validator("longitud")
    @classmethod
    def validar_longitud(cls, v: Decimal) -> Decimal:
        if v < Decimal("-180") or v > Decimal("180"):
            raise ValueError("La longitud debe estar entre -180 y 180.")
        return v


class RegistrarFincaDTO(BaseDTO):
    nombre: str
    ubicacion: UbicacionFincaDTO
    tamano_h: Decimal
    id_usuario: Optional[int] = None

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

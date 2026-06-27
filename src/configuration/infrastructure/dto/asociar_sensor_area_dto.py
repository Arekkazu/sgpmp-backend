"""DTO de entrada para asociar un sensor a un área productiva (POST /{id}/asociar RF-22)."""
from __future__ import annotations

from pydantic import field_validator

from src.shared.base_dto import BaseDTO


class AsociarSensorAreaDTO(BaseDTO):
    id_dispositivo_iot: int
    id_infraestructura: int
    punto_instalacion: str

    @field_validator("punto_instalacion")
    @classmethod
    def validar_punto(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El punto de instalación es obligatorio.")
        if len(v.strip()) > 100:
            raise ValueError("El punto de instalación no puede superar los 100 caracteres.")
        return v

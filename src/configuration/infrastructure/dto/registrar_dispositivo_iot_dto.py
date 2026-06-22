"""DTO de entrada para registrar un dispositivo IoT (POST RF-21)."""
from __future__ import annotations

from pydantic import field_validator

from src.shared.base_dto import BaseDTO


class RegistrarDispositivoIotDTO(BaseDTO):
    serial: str
    descripcion: str
    id_infraestructura: int
    es_activo: bool = True

    @field_validator("serial")
    @classmethod
    def validar_serial(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El serial del dispositivo es obligatorio.")
        if len(v.strip()) > 50:
            raise ValueError("El serial no puede superar los 50 caracteres.")
        return v

    @field_validator("descripcion")
    @classmethod
    def validar_descripcion(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("La descripción del dispositivo es obligatoria.")
        if len(v.strip()) > 100:
            raise ValueError("La descripción no puede superar los 100 caracteres.")
        return v

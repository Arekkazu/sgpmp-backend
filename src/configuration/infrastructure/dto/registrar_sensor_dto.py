"""DTO de entrada para registrar un sensor en un dispositivo IoT (POST /{id}/sensores)."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import field_validator

from src.shared.base_dto import BaseDTO

CategoriaSensor = Literal["HUMEDAD", "TEMPERATURA", "OXIGENO", "PH", "AMONIACO", "SALINIDAD", "LUMINOSIDAD"]


class RegistrarSensorDTO(BaseDTO):
    nombre: str
    categoria: Optional[CategoriaSensor] = None

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El nombre del sensor es obligatorio.")
        if len(v.strip()) > 100:
            raise ValueError("El nombre del sensor no puede superar los 100 caracteres.")
        return v

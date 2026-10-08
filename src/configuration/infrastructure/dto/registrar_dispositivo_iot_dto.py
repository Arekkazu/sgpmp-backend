"""DTO de entrada para registrar un dispositivo IoT (POST RF-21)."""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Optional

from pydantic import PositiveInt, field_validator

from src.shared.base_dto import BaseDTO

# INC-M09-21-G125-01: letras (con tildes/ñ), números, espacio y puntuación segura.
# Sin comillas, `<`/`>`, `;` ni `=` — bloquea tanto sintaxis de inyección SQL
# como etiquetas de script en un campo de texto libre.
_FORMATO_DESCRIPCION = re.compile(r"^[A-Za-zÁÉÍÓÚáéíóúÑñ0-9 .,()/_-]+$")


class RegistrarDispositivoIotDTO(BaseDTO):
    serial: str
    descripcion: str
    id_infraestructura: int
    id_tipo_dispositivo: int
    es_activo: bool = True
    # RF-21: Gateway Edge que lo atiende (opcional; nunca para un GATEWAY_EDGE).
    id_dispositivo_gateway: Optional[PositiveInt] = None
    # RF-21 v2.0 (RFC-011): obligatorios si el tipo es CAMARA; el use case los
    # valida (400) o los ignora para un SENSOR, porque la categoría la da el tipo.
    resolucion: Optional[str] = None
    fps: Optional[int] = None
    area_cobertura_m2: Optional[Decimal] = None

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
        if not _FORMATO_DESCRIPCION.match(v.strip()):
            raise ValueError(
                "La descripción solo puede contener letras, números, espacios y la puntuación .,()/_-"
            )
        return v

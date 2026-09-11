"""DTO de entrada para editar una patología del catálogo (Flujo F — RF-16).

Incluye ``fecha_actualizacion`` para control de concurrencia optimista (FA-07).
"""
from datetime import datetime
from typing import Optional
import re

from pydantic import field_validator

from src.shared.base_dto import BaseDTO

_NOMBRE_PATOLOGIA = re.compile(r"^[A-Za-zÁÉÍÓÚáéíóúÑñ][A-Za-zÁÉÍÓÚáéíóúÑñ0-9 \-(). ]*$")


class EditarPatologiaDTO(BaseDTO):
    nombre: str
    descripcion: Optional[str] = None
    fecha_actualizacion: Optional[datetime] = None

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3 or len(v) > 60:
            raise ValueError("El nombre de la patología debe tener entre 3 y 60 caracteres.")
        if not _NOMBRE_PATOLOGIA.match(v):
            raise ValueError("El nombre de la patología contiene caracteres no permitidos.")
        return v

    @field_validator("descripcion")
    @classmethod
    def validar_descripcion(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 255:
            raise ValueError("La descripción no puede superar los 255 caracteres.")
        return v

"""DTO de entrada para actualizar la configuración operativa global (PATCH RF-18).

Incluye ``fecha_actualizacion`` como token de concurrencia optimista.
"""
from datetime import datetime

from pydantic import field_validator

from src.shared.base_dto import BaseDTO


class ActualizarConfiguracionDTO(BaseDTO):
    frecuencia_muestreo: int
    heartbeat: int
    fecha_actualizacion: datetime

    @field_validator("frecuencia_muestreo", "heartbeat")
    @classmethod
    def validar_entero_positivo(cls, v: int) -> int:
        if not isinstance(v, int) or isinstance(v, bool) or v <= 0:
            raise ValueError(
                f"Debe ser un número entero positivo mayor a 0. Valor recibido: {v}."
            )
        return v

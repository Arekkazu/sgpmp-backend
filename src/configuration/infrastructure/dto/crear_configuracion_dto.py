"""DTO de entrada para crear la configuración operativa global (POST RF-18)."""
from pydantic import field_validator

from src.shared.base_dto import BaseDTO


class CrearConfiguracionDTO(BaseDTO):
    frecuencia_muestreo: int
    heartbeat: int

    @field_validator("frecuencia_muestreo", "heartbeat")
    @classmethod
    def validar_entero_positivo(cls, v: int) -> int:
        if not isinstance(v, int) or isinstance(v, bool) or v <= 0:
            raise ValueError(
                f"Debe ser un número entero positivo mayor a 0. Valor recibido: {v}."
            )
        return v

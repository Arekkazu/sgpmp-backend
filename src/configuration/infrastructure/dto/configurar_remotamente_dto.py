"""DTO de entrada para configurar remotamente un dispositivo IoT (POST /{id}/configurar RF-23)."""
from __future__ import annotations

from pydantic import field_validator, model_validator

from src.shared.base_dto import BaseDTO


class ConfigurarRemotamenteDTO(BaseDTO):
    frecuencia_captura: int
    intervalo_transmision: int

    @field_validator("frecuencia_captura", "intervalo_transmision")
    @classmethod
    def validar_positivo(cls, v: int) -> int:
        if v < 1:
            raise ValueError("El valor debe ser un entero positivo (mínimo 1 minuto).")
        return v

    @model_validator(mode="after")
    def validar_coherencia_tiempos(self) -> ConfigurarRemotamenteDTO:
        """RF-23, flujo alterno "Inconsistencia lógica de tiempos" -> HTTP 400.

        Vive en el DTO y no en el use case precisamente porque el RF lo clasifica
        como 400: un `@model_validator` sale por `request_validation_error_handler`,
        que es el único camino a 400 sin código de negocio propio.
        """
        if self.intervalo_transmision < self.frecuencia_captura:
            raise ValueError(
                "Conflicto lógico: El intervalo de transmisión "
                f"({self.intervalo_transmision} min) no puede ser menor a la frecuencia "
                f"de captura de datos ({self.frecuencia_captura} min). Ajuste los valores "
                "para asegurar la coherencia del flujo."
            )
        return self

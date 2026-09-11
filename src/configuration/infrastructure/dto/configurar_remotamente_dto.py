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
        if self.intervalo_transmision < self.frecuencia_captura:
            raise ValueError(
                "El intervalo de transmisión no puede ser menor a la frecuencia de captura. "
                f"frecuencia_captura={self.frecuencia_captura}, intervalo_transmision={self.intervalo_transmision}."
            )
        return self

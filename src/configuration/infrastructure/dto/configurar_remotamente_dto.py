"""DTO de entrada para configurar remotamente un dispositivo IoT (POST /{id}/configurar RF-23)."""
from __future__ import annotations

from typing import Optional

from pydantic import ConfigDict, field_validator, model_validator

from src.shared.base_dto import BaseDTO


class ConfigurarRemotamenteDTO(BaseDTO):
    """Parámetros de configuración según la categoría del dispositivo (RF-23 v1.1).

    SENSOR: ``frecuencia_captura`` e ``intervalo_transmision`` (minutos), dentro del
    rango de su tipo. CAMARA: ``fps`` (1–60, RF-21). Qué juego corresponde lo decide
    el use case con la categoría del tipo del dispositivo.
    """
    # INC-M09-66-G69 (#492): RF-23 solo define estos parámetros. Un campo ajeno
    # (p. ej. `protocolo`) se ignoraba y la API respondía 202 como si lo hubiera
    # aplicado; ahora es 400. LoRaWAN es la red entre el dispositivo y su
    # gateway, no un parámetro que el backend envíe: el backend solo habla MQTT.
    model_config = ConfigDict(extra="forbid")

    frecuencia_captura: Optional[int] = None
    intervalo_transmision: Optional[int] = None
    fps: Optional[int] = None

    @field_validator("frecuencia_captura", "intervalo_transmision")
    @classmethod
    def validar_positivo(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 1:
            raise ValueError("El valor debe ser un entero positivo (mínimo 1 minuto).")
        return v

    @field_validator("fps")
    @classmethod
    def validar_fps(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not 1 <= v <= 60:
            raise ValueError("fps debe estar entre 1 y 60 cuadros por segundo.")
        return v

    @model_validator(mode="after")
    def validar_coherencia_tiempos(self) -> ConfigurarRemotamenteDTO:
        """RF-23, flujo alterno "Inconsistencia lógica de tiempos" -> HTTP 400.

        Vive en el DTO y no en el use case precisamente porque el RF lo clasifica
        como 400: un `@model_validator` sale por `request_validation_error_handler`,
        que es el único camino a 400 sin código de negocio propio.
        """
        if (
            self.frecuencia_captura is not None
            and self.intervalo_transmision is not None
            and self.intervalo_transmision < self.frecuencia_captura
        ):
            raise ValueError(
                "Conflicto lógico: El intervalo de transmisión "
                f"({self.intervalo_transmision} min) no puede ser menor a la frecuencia "
                f"de captura de datos ({self.frecuencia_captura} min). Ajuste los valores "
                "para asegurar la coherencia del flujo."
            )
        return self

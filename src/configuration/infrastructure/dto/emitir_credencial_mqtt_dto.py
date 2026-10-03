"""DTO de entrada para emitir o rotar la credencial MQTT de una Raspberry (RF-23, TC-M09-250/251)."""
from __future__ import annotations

from pydantic import Field, PositiveInt

from src.shared.base_dto import BaseDTO


class EmitirCredencialMqttDTO(BaseDTO):
    # Otros dispositivos IoT que transmite la misma Raspberry (modelo "serial por
    # ESP32"). Vacío en el modelo "serial por sitio": la Raspberry es el
    # dispositivo del path.
    ids_dispositivos_adicionales: list[PositiveInt] = Field(default_factory=list, max_length=50)

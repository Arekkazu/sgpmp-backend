"""Puerto (ABC) para comunicación MQTT con dispositivos IoT (RF-23).

La implementación real enviaría el payload al broker MQTT sobre LoRaWAN.
El stub retorna siempre False (dispositivo offline) hasta que se integre el broker real.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class MqttPort(ABC):

    @abstractmethod
    def enviar_configuracion(self, id_dispositivo_iot: int, payload: dict) -> bool:
        """Retorna True si el dispositivo confirmó recepción, False si está offline."""
        ...

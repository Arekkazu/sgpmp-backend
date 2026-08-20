"""Puerto (ABC) para comunicación MQTT con dispositivos IoT (RF-23).

La implementación real (MqttHttpAdapter) llama al broker MQTT
(BROKER-MQTT-SGPMP), que publica el comando y espera de forma acotada la
confirmación (ACK) del dispositivo.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ResultadoEnvioMqtt:
    """Resultado de intentar enviar una configuración a un dispositivo IoT."""

    estado: str  # "APLICADA" | "PENDIENTE" | "NO_CONF"
    mensaje: str


class MqttPort(ABC):

    @abstractmethod
    def enviar_configuracion(self, serial: str, payload: dict) -> ResultadoEnvioMqtt:
        """Intenta enviar la configuración al dispositivo identificado por `serial`.

        Nunca lanza: ante cualquier fallo de comunicación (broker caído,
        timeout de red) degrada a ResultadoEnvioMqtt(estado="PENDIENTE", ...)
        para no romper el flujo de negocio -- la configuración ya quedó
        persistida como PENDIENTE antes de llamar acá.
        """
        ...

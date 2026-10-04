"""Puerto (ABC) para comunicación MQTT con dispositivos IoT (RF-23).

La implementación real (MqttHttpAdapter) llama al broker MQTT
(BROKER-MQTT-SGPMP) por HTTPS: este backend nunca habla MQTT. El broker
publica el comando y espera de forma acotada la confirmación (ACK) del
dispositivo, y gestiona las credenciales MQTT de los Gateway Edge.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ResultadoEnvioMqtt:
    """Resultado de intentar enviar una configuración a un dispositivo IoT."""

    estado: str  # "APLICADA" | "PENDIENTE" | "NO_CONF"
    mensaje: str


@dataclass(frozen=True)
class CredencialMqtt:
    """Credencial MQTT recién emitida para un Gateway Edge (TC-M09-250/251).

    `password` existe solo en esta respuesta: no se persiste en ningún lado.
    """

    usuario: str
    password: str
    seriales: list[str]


@dataclass(frozen=True)
class EstadoCredencialMqtt:
    usuario: str
    habilitada: bool
    conectada: bool
    seriales: list[str]


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

    # A diferencia de enviar_configuracion, las operaciones de credencial NO
    # degradan en silencio: si el broker no responde lanzan
    # ServiceUnavailableError, porque quien las pide necesita el resultado.

    @abstractmethod
    def emitir_credencial(self, serial: str) -> CredencialMqtt:
        """Crea o rota la credencial de `serial` (usuario MQTT) con permiso sobre
        sus topics y los de los dispositivos que atiende según modulo9."""
        ...

    @abstractmethod
    def sincronizar_credencial(self, serial: str) -> None:
        """Recalcula desde modulo9 los topics de la credencial de `serial` sin
        rotar la clave. No hace nada si `serial` no tiene credencial."""
        ...

    @abstractmethod
    def consultar_credencial(self, serial: str) -> Optional[EstadoCredencialMqtt]:
        """None si `serial` no tiene credencial propia."""
        ...

    @abstractmethod
    def revocar_credencial(self, serial: str) -> None:
        """Deshabilita la credencial de `serial` y le quita sus topics a cualquier
        Gateway Edge que lo atienda. Idempotente."""
        ...

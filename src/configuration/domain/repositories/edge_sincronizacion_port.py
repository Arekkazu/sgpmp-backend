"""Puerto (ABC) para propagar umbrales ambientales hacia el Nodo Edge (RF-17).

INC-M09-104-G29: el umbral se envía a cada Gateway Edge de las áreas de su
especie (``DestinoEdgeRepository``), por el broker MQTT
(``BROKER-MQTT-SGPMP``, ``POST /v1/commands`` con ``origen: "umbral"``). A
diferencia de ``MqttPort`` (RF-23), un fallo de comunicación con el broker NO
degrada a ``PENDIENTE``: el RF-17 exige reportarlo (500).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.configuration.domain.repositories.mqtt_port import ResultadoEnvioMqtt

#: El ambiente no tiene integración con el broker: no hubo intento de propagar.
ESTADO_SIN_INTEGRACION = "SIN_INTEGRACION"


class EdgeSincronizacionPort(ABC):

    @abstractmethod
    def propagar_umbral(self, seriales_gateway: list[str], payload: dict) -> dict[str, ResultadoEnvioMqtt]:
        """Envía el umbral a cada Gateway Edge y devuelve el resultado de cada uno.

        Nunca lanza -- el umbral ya quedó persistido antes de llamar acá. El
        ``estado`` de cada resultado:

        - ``"APLICADA"``: ese Edge confirmó (ACK).
        - ``"PENDIENTE"``: el broker sabe que ese Edge está desconectado y no
          publicó (TC-M09-63). Para RF-17 es un error de sincronización: el
          Edge sigue con el umbral anterior.
        - ``"NO_CONF"``: se intentó y falló (broker caído, timeout, sin ACK).
          Es el "Error de sincronización con el Nodo Edge" de RF-17.
        - ``ESTADO_SIN_INTEGRACION``: el ambiente no tiene broker configurado;
          no hubo intento, así que no es un error.

        Un adaptador real NO debe devolver ``PENDIENTE`` ante un fallo de
        comunicación: ocultaría el 500 que el RF exige.
        """
        ...

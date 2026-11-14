"""Puerto (ABC): enviar la configuración del motor a los nodos Edge por el broker (DEV-09).

Contrato BRK-05 (``BROKER-MQTT-SGPMP``): ``POST /v1/commands`` con
``origen: "config_motor"``; el broker publica ``tipo_comando: "CONFIG_MOTOR_IA"``
y espera el ``ACK_CONFIG_MOTOR``, cuyo ``config_version`` devuelve en la respuesta.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.prediction.domain.entities.sincronizacion_nodo_edge import ResultadoEnvioConfigMotor


class ConfigMotorEdgePort(ABC):
    @abstractmethod
    def propagar_config(self, seriales: list[str], payload: dict) -> dict[str, ResultadoEnvioConfigMotor]:
        """Envía la configuración a cada nodo y devuelve el veredicto de cada uno. Nunca lanza.

        ``estado``: ``APLICADA`` (llegó el ACK), ``PENDIENTE`` (nodo desconectado,
        no se publicó), ``NO_CONF`` (broker caído, error HTTP o sin ACK) o
        ``SIN_INTEGRACION`` (el ambiente no tiene broker configurado).
        """
        ...

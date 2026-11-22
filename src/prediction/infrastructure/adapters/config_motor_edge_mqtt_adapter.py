"""Adaptador de ``ConfigMotorEdgePort``: configuración del motor a los nodos vía broker (DEV-09).

Mismo patrón que ``EdgeSincronizacionMqttAdapter`` (umbrales, RF-17), con el
comando de BRK-05: por cada nodo llama a ``POST {MQTT_BROKER_URL}/v1/commands``
con ``origen: "config_motor"``. El broker lo publica con
``tipo_comando: "CONFIG_MOTOR_IA"``, espera el ``ACK_CONFIG_MOTOR`` y responde
el veredicto (APLICADA / PENDIENTE si el nodo no está conectado / NO_CONF sin
ACK) junto con el ``config_version`` que informó el nodo, siempre con HTTP 200.

Broker caído o error HTTP: ``NO_CONF``. Sin ``MQTT_BROKER_URL``/``MQTT_BROKER_TOKEN``:
``SIN_INTEGRACION`` (no hubo intento). Los nodos se llaman en paralelo y cada
llamada pasa por el semáforo global de las llamadas al broker (RF-23).
"""
from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import httpx

from src.configuration.infrastructure.adapters.mqtt_http_adapter import (
    _TIMEOUT_HTTP_SEGUNDOS,
    _semaforo_llamadas_broker,
)
from src.prediction.domain.entities.sincronizacion_nodo_edge import (
    BROKER_NO_CONF,
    SIN_INTEGRACION,
    ResultadoEnvioConfigMotor,
)
from src.prediction.domain.repositories.config_motor_edge_port import ConfigMotorEdgePort

logger = logging.getLogger(__name__)

ORIGEN_CONFIG_MOTOR = "config_motor"
_MAX_NODOS_EN_PARALELO = 8
_MENSAJE_SIN_INTEGRACION = (
    "La integración con el broker MQTT no está configurada en este ambiente. "
    "La configuración queda pendiente de sincronización."
)
_MENSAJE_BROKER_NO_DISPONIBLE = "El broker MQTT no propagó la configuración del motor."


def _config_version(valor) -> Optional[int]:
    # bool es int en Python: un `true` no es una versión (mismo criterio que el broker).
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


class ConfigMotorEdgeMqttAdapter(ConfigMotorEdgePort):

    def __init__(self) -> None:
        self._base_url = os.environ.get("MQTT_BROKER_URL", "")
        self._token = os.environ.get("MQTT_BROKER_TOKEN", "")

    def propagar_config(self, seriales: list[str], payload: dict) -> dict[str, ResultadoEnvioConfigMotor]:
        if not seriales:
            return {}
        if not self._base_url or not self._token:
            logger.error("MQTT_BROKER_URL/MQTT_BROKER_TOKEN no configurados -- configuración del motor no propagada.")
            return {
                serial: ResultadoEnvioConfigMotor(estado=SIN_INTEGRACION, mensaje=_MENSAJE_SIN_INTEGRACION)
                for serial in seriales
            }

        hilos = min(len(seriales), _MAX_NODOS_EN_PARALELO)
        with ThreadPoolExecutor(max_workers=hilos) as ejecutor:
            resultados = ejecutor.map(lambda serial: self._enviar(serial, payload), seriales)
            return dict(zip(seriales, resultados))

    def _enviar(self, serial: str, payload: dict) -> ResultadoEnvioConfigMotor:
        with _semaforo_llamadas_broker:
            try:
                respuesta = httpx.post(
                    f"{self._base_url}/v1/commands",
                    json={"origen": ORIGEN_CONFIG_MOTOR, "serial": serial, **payload},
                    headers={"Authorization": f"Bearer {self._token}"},
                    timeout=_TIMEOUT_HTTP_SEGUNDOS,
                )
                respuesta.raise_for_status()
                cuerpo = respuesta.json()
                return ResultadoEnvioConfigMotor(
                    estado=cuerpo["estado"],
                    mensaje=cuerpo["mensaje"],
                    config_version=_config_version(cuerpo.get("config_version")),
                    publicado=bool(cuerpo.get("topic")),
                )
            except httpx.HTTPStatusError as exc:
                causa = f"el broker respondió HTTP {exc.response.status_code}: {exc.response.text[:200]}"
            except httpx.HTTPError as exc:
                causa = f"sin respuesta del broker ({type(exc).__name__})"
            except (ValueError, KeyError) as exc:
                causa = f"respuesta inválida del broker ({type(exc).__name__})"
            logger.error("Configuración del motor no propagada a %s: %s", serial, causa)
            return ResultadoEnvioConfigMotor(
                estado=BROKER_NO_CONF, mensaje=f"{_MENSAJE_BROKER_NO_DISPONIBLE} Causa: {causa}.", publicado=False
            )

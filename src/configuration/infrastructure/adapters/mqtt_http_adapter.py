"""Adaptador real de ``MqttPort`` -- llama a BROKER-MQTT-SGPMP por HTTP (RF-23).

El broker publica el comando en MQTT y espera hasta ~30s el ACK del
dispositivo antes de responder. Este adaptador nunca lanza: si la llamada
falla (broker caído, timeout de red, error HTTP) degrada a "PENDIENTE",
mismo espíritu que ``src/shared/firebase.py`` -- la fila ya quedó persistida
como PENDIENTE antes de llamar acá, así que un broker inalcanzable no debe
romper el flujo de negocio.
"""
from __future__ import annotations

import logging
import os
import threading

import httpx

from src.configuration.domain.repositories.mqtt_port import MqttPort, ResultadoEnvioMqtt

logger = logging.getLogger(__name__)

# ponytail: cap de concurrencia global -- este endpoint es sincrono (Session,
# no AsyncSession) y una espera de hasta ~35s ocupa un hilo del threadpool
# compartido de Starlette, usado por *todos* los endpoints del proceso. El
# cap evita que varias configuraciones concurrentes agoten ese pool y
# degraden endpoints no relacionados. Si este endpoint se vuelve de alto
# trafico, la solucion real es mover el router a async def/AsyncSession, no
# aplica para esta entrega.
_semaforo_llamadas_broker = threading.Semaphore(10)

_TIMEOUT_HTTP_SEGUNDOS = 35.0
_MENSAJE_BROKER_NO_DISPONIBLE = "No se pudo contactar al broker MQTT. La configuración quedará pendiente."


class MqttHttpAdapter(MqttPort):

    def __init__(self) -> None:
        self._base_url = os.environ.get("MQTT_BROKER_URL", "")
        self._token = os.environ.get("MQTT_BROKER_TOKEN", "")

    def enviar_configuracion(self, serial: str, payload: dict) -> ResultadoEnvioMqtt:
        if not self._base_url or not self._token:
            logger.error("MQTT_BROKER_URL/MQTT_BROKER_TOKEN no configurados -- broker omitido.")
            return ResultadoEnvioMqtt(estado="PENDIENTE", mensaje=_MENSAJE_BROKER_NO_DISPONIBLE)

        with _semaforo_llamadas_broker:
            try:
                respuesta = httpx.post(
                    f"{self._base_url}/v1/commands",
                    json={"origen": "configuracion", "serial": serial, **payload},
                    headers={"Authorization": f"Bearer {self._token}"},
                    timeout=_TIMEOUT_HTTP_SEGUNDOS,
                )
                respuesta.raise_for_status()
                cuerpo = respuesta.json()
                return ResultadoEnvioMqtt(estado=cuerpo["estado"], mensaje=cuerpo["mensaje"])
            except httpx.HTTPError as exc:
                logger.error("Broker MQTT no disponible al configurar %s: %r", serial, exc)
                return ResultadoEnvioMqtt(estado="PENDIENTE", mensaje=_MENSAJE_BROKER_NO_DISPONIBLE)

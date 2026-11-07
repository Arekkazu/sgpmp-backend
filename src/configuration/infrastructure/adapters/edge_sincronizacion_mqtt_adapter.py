"""Adaptador real de ``EdgeSincronizacionPort`` — umbrales al Gateway Edge vía broker (RF-17).

INC-M09-104-G29: reemplaza a ``EdgeSincronizacionStubAdapter``. Por cada
Gateway Edge llama a ``POST {MQTT_BROKER_URL}/v1/commands`` con
``origen: "umbral"``; el broker (``BROKER-MQTT-SGPMP``) lo publica en
``sgpmp/<serial>/command`` con ``tipo_comando: "UMBRAL_AMBIENTAL"`` y espera
hasta 30 s el ``ACK_UMBRAL`` del Edge (contrato en
``INTEGRACION_DISPOSITIVOS_RF17.md`` de ese repo). El broker responde el
veredicto (APLICADA / PENDIENTE si el Edge no está conectado / NO_CONF sin ACK)
en el cuerpo, siempre con HTTP 200.

Diferencia deliberada con ``MqttHttpAdapter`` (RF-23): si el broker no responde
o devuelve un error HTTP, el resultado es ``NO_CONF``, no ``PENDIENTE`` -- se
intentó propagar y falló, y RF-17 exige reportarlo (500). Solo cuando la
integración no está configurada en el ambiente (sin ``MQTT_BROKER_URL``/
``MQTT_BROKER_TOKEN``) devuelve ``ESTADO_SIN_INTEGRACION``: ahí no hubo intento.

Los Gateway se llaman en paralelo para que N destinos no sumen N esperas de
ACK; cada llamada pasa por el mismo semáforo global que RF-23, que protege el
threadpool compartido de Starlette.

DEV-10 (RF-20, D-06): el mismo transporte lleva el ``tipo_modelo_asignado`` de
un área con ``origen: "tipo_modelo"`` (BRK-05, ``tipo_comando:
"TIPO_MODELO_ASIGNADO"``, ``ACK_TIPO_MODELO``).
"""
from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import httpx

from src.configuration.domain.repositories.edge_sincronizacion_port import (
    ESTADO_SIN_INTEGRACION,
    EdgeSincronizacionPort,
)
from src.configuration.domain.repositories.mqtt_port import ResultadoEnvioMqtt
from src.configuration.infrastructure.adapters.mqtt_http_adapter import (
    _TIMEOUT_HTTP_SEGUNDOS,
    _semaforo_llamadas_broker,
)

logger = logging.getLogger(__name__)

_MAX_GATEWAYS_EN_PARALELO = 8


@dataclass(frozen=True)
class _Comando:
    origen: str
    que: str
    mensaje_sin_integracion: str
    mensaje_no_disponible: str


_UMBRAL = _Comando(
    origen="umbral",
    que="umbral",
    mensaje_sin_integracion=(
        "La integración con el broker MQTT no está configurada en este ambiente. "
        "El umbral quedó guardado y pendiente de sincronización."
    ),
    mensaje_no_disponible="El broker MQTT no propagó el umbral.",
)
# DEV-10 (RF-20, D-06; BRK-05): tipo_comando TIPO_MODELO_ASIGNADO, confirmación ACK_TIPO_MODELO.
_TIPO_MODELO = _Comando(
    origen="tipo_modelo",
    que="tipo_modelo_asignado",
    mensaje_sin_integracion=(
        "La integración con el broker MQTT no está configurada en este ambiente. "
        "El tipo_modelo_asignado quedó guardado y pendiente de sincronización."
    ),
    mensaje_no_disponible="El broker MQTT no propagó el tipo_modelo_asignado.",
)


class EdgeSincronizacionMqttAdapter(EdgeSincronizacionPort):

    def __init__(self) -> None:
        self._base_url = os.environ.get("MQTT_BROKER_URL", "")
        self._token = os.environ.get("MQTT_BROKER_TOKEN", "")

    def propagar_umbral(self, seriales_gateway: list[str], payload: dict) -> dict[str, ResultadoEnvioMqtt]:
        return self._propagar(seriales_gateway, payload, _UMBRAL)

    def propagar_tipo_modelo(self, seriales_gateway: list[str], payload: dict) -> dict[str, ResultadoEnvioMqtt]:
        return self._propagar(seriales_gateway, payload, _TIPO_MODELO)

    def _propagar(self, seriales_gateway: list[str], payload: dict, comando: _Comando) -> dict[str, ResultadoEnvioMqtt]:
        if not seriales_gateway:
            return {}
        if not self._base_url or not self._token:
            logger.error("MQTT_BROKER_URL/MQTT_BROKER_TOKEN no configurados -- %s no propagado.", comando.que)
            return {
                serial: ResultadoEnvioMqtt(estado=ESTADO_SIN_INTEGRACION, mensaje=comando.mensaje_sin_integracion)
                for serial in seriales_gateway
            }

        hilos = min(len(seriales_gateway), _MAX_GATEWAYS_EN_PARALELO)
        with ThreadPoolExecutor(max_workers=hilos) as ejecutor:
            resultados = ejecutor.map(lambda serial: self._enviar(serial, payload, comando), seriales_gateway)
            return dict(zip(seriales_gateway, resultados))

    def _enviar(self, serial: str, payload: dict, comando: _Comando) -> ResultadoEnvioMqtt:
        with _semaforo_llamadas_broker:
            try:
                respuesta = httpx.post(
                    f"{self._base_url}/v1/commands",
                    json={"origen": comando.origen, "serial": serial, **payload},
                    headers={"Authorization": f"Bearer {self._token}"},
                    timeout=_TIMEOUT_HTTP_SEGUNDOS,
                )
                respuesta.raise_for_status()
                cuerpo = respuesta.json()
                return ResultadoEnvioMqtt(
                    estado=cuerpo["estado"], mensaje=cuerpo["mensaje"], publicado=bool(cuerpo.get("topic"))
                )
            # INC-M09-70-G29: la causa va en el mensaje (motivo del umbral y
            # bitácora IoT), no solo en el log del contenedor.
            except httpx.HTTPStatusError as exc:
                causa = f"el broker respondió HTTP {exc.response.status_code}: {exc.response.text[:200]}"
            except httpx.HTTPError as exc:
                causa = f"sin respuesta del broker ({type(exc).__name__})"
            except (ValueError, KeyError) as exc:
                causa = f"respuesta inválida del broker ({type(exc).__name__})"
            logger.error("%s no propagado a %s: %s", comando.que.capitalize(), serial, causa)
            return ResultadoEnvioMqtt(
                estado="NO_CONF", mensaje=f"{comando.mensaje_no_disponible} Causa: {causa}.", publicado=False
            )

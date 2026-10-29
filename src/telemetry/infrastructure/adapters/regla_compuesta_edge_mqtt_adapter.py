"""Adaptador de ``ReglaCompuestaEdgePort``: reglas compuestas al Gateway Edge vía broker (DEV-08).

Igual que ``EdgeSincronizacionMqttAdapter`` (umbrales, RF-17), con el comando
de BRK-05: por cada Gateway Edge llama a ``POST {MQTT_BROKER_URL}/v1/commands``
con ``origen: "regla_compuesta"``. El broker (``BROKER-MQTT-SGPMP``) lo publica
en ``sgpmp/<serial>/command`` con ``tipo_comando: "REGLA_COMPUESTA"`` y espera
el ``ACK_REGLA`` del Edge; responde el veredicto (APLICADA / PENDIENTE si el
Edge no está conectado / NO_CONF sin ACK) en el cuerpo, siempre con HTTP 200.

Si el broker no responde o devuelve un error HTTP, el resultado es ``NO_CONF``:
se intentó y falló. Sin ``MQTT_BROKER_URL``/``MQTT_BROKER_TOKEN`` devuelve
``SIN_INTEGRACION``: ahí no hubo intento. Los Gateway se llaman en paralelo y
cada llamada pasa por el semáforo global de las llamadas al broker (RF-23).
"""
from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor

import httpx

from src.configuration.infrastructure.adapters.mqtt_http_adapter import (
    _TIMEOUT_HTTP_SEGUNDOS,
    _semaforo_llamadas_broker,
)
from src.telemetry.domain.entities.sincronizacion_regla_edge import (
    ESTADO_NO_CONF,
    ESTADO_SIN_INTEGRACION,
    ResultadoPropagacionEdge,
)
from src.telemetry.domain.repositories.regla_compuesta_edge_port import ReglaCompuestaEdgePort

logger = logging.getLogger(__name__)

ORIGEN_REGLA_COMPUESTA = "regla_compuesta"
_MAX_GATEWAYS_EN_PARALELO = 8
_MENSAJE_SIN_INTEGRACION = (
    "La integración con el broker MQTT no está configurada en este ambiente. "
    "La regla queda pendiente de sincronización."
)
_MENSAJE_BROKER_NO_DISPONIBLE = "El broker MQTT no propagó la regla."


class ReglaCompuestaEdgeMqttAdapter(ReglaCompuestaEdgePort):

    def __init__(self) -> None:
        self._base_url = os.environ.get("MQTT_BROKER_URL", "")
        self._token = os.environ.get("MQTT_BROKER_TOKEN", "")

    def propagar_regla(self, seriales_gateway: list[str], payload: dict) -> dict[str, ResultadoPropagacionEdge]:
        if not seriales_gateway:
            return {}
        if not self._base_url or not self._token:
            logger.error("MQTT_BROKER_URL/MQTT_BROKER_TOKEN no configurados -- regla no propagada.")
            return {
                serial: ResultadoPropagacionEdge(estado=ESTADO_SIN_INTEGRACION, mensaje=_MENSAJE_SIN_INTEGRACION)
                for serial in seriales_gateway
            }

        hilos = min(len(seriales_gateway), _MAX_GATEWAYS_EN_PARALELO)
        with ThreadPoolExecutor(max_workers=hilos) as ejecutor:
            resultados = ejecutor.map(lambda serial: self._enviar(serial, payload), seriales_gateway)
            return dict(zip(seriales_gateway, resultados))

    def _enviar(self, serial: str, payload: dict) -> ResultadoPropagacionEdge:
        with _semaforo_llamadas_broker:
            try:
                respuesta = httpx.post(
                    f"{self._base_url}/v1/commands",
                    json={"origen": ORIGEN_REGLA_COMPUESTA, "serial": serial, **payload},
                    headers={"Authorization": f"Bearer {self._token}"},
                    timeout=_TIMEOUT_HTTP_SEGUNDOS,
                )
                respuesta.raise_for_status()
                cuerpo = respuesta.json()
                return ResultadoPropagacionEdge(
                    estado=cuerpo["estado"], mensaje=cuerpo["mensaje"], publicado=bool(cuerpo.get("topic"))
                )
            except httpx.HTTPStatusError as exc:
                causa = f"el broker respondió HTTP {exc.response.status_code}: {exc.response.text[:200]}"
            except httpx.HTTPError as exc:
                causa = f"sin respuesta del broker ({type(exc).__name__})"
            except (ValueError, KeyError) as exc:
                causa = f"respuesta inválida del broker ({type(exc).__name__})"
            logger.error("Regla compuesta no propagada a %s: %s", serial, causa)
            return ResultadoPropagacionEdge(
                estado=ESTADO_NO_CONF, mensaje=f"{_MENSAJE_BROKER_NO_DISPONIBLE} Causa: {causa}.", publicado=False
            )

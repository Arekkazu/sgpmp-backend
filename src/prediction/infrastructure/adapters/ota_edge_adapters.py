"""Adaptadores del orquestador OTA (DEV-15, D6 de AIOT-DEV-03).

- ``NodoOtaM09Adapter``: serial de los nodos objetivo en ``modulo9.dispositivos_iot``.
  Corre ``como_sistema`` porque ``modulo9`` tiene RLS forzada.
- ``AvisoOtaBrokerAdapter``: ``POST {MQTT_BROKER_URL}/v1/ota/notify`` (BRK-08); el
  broker publica ``sgpmp/<serial>/ota/notify`` y responde 202 sin esperar la
  instalación.
- ``UrlDescargaHmacAdapter``: URL temporal y firmada del artefacto. La firma es un
  HMAC-SHA256 de ``"<id_despliegue>:<expira_epoch>"`` con ``OTA_URL_SECRET``; el
  backend la sirve en ``GET /prediccion/ota/artefactos/{id}`` con soporte de Range.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
from datetime import datetime
from urllib.parse import urlencode

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.configuration.infrastructure.adapters.mqtt_http_adapter import (
    _TIMEOUT_HTTP_SEGUNDOS,
    _semaforo_llamadas_broker,
)
from src.prediction.domain.repositories.ota_edge_port import (
    AvisoOtaPort,
    NodoOtaPort,
    ResultadoAvisoOta,
    UrlDescargaPort,
)
from src.shared.database import como_sistema

logger = logging.getLogger(__name__)

_SQL_SERIALES_ACTIVOS = text(
    "SELECT id_dispositivo_iot, serial FROM modulo9.dispositivos_iot "
    "WHERE id_dispositivo_iot = ANY(:ids) AND es_activo"
)


class NodoOtaM09Adapter(NodoOtaPort):

    def __init__(self, db: Session) -> None:
        self._db = db

    def obtener_seriales(self, ids_dispositivo: list[int]) -> dict[int, str]:
        with como_sistema(self._db):
            return dict(self._db.execute(_SQL_SERIALES_ACTIVOS, {"ids": ids_dispositivo}).tuples().all())


class AvisoOtaBrokerAdapter(AvisoOtaPort):

    def __init__(self) -> None:
        self._base_url = os.environ.get("MQTT_BROKER_URL", "")
        self._token = os.environ.get("MQTT_BROKER_TOKEN", "")

    def notificar(self, aviso: dict) -> ResultadoAvisoOta:
        if not self._base_url or not self._token:
            return ResultadoAvisoOta(
                publicado=False,
                mensaje="La integración con el broker MQTT no está configurada en este ambiente.",
            )
        with _semaforo_llamadas_broker:
            try:
                respuesta = httpx.post(
                    f"{self._base_url}/v1/ota/notify",
                    json=aviso,
                    headers={"Authorization": f"Bearer {self._token}"},
                    timeout=_TIMEOUT_HTTP_SEGUNDOS,
                )
                respuesta.raise_for_status()
                cuerpo = respuesta.json()
                return ResultadoAvisoOta(
                    publicado=True, mensaje="Aviso ota/notify publicado.", id_mensaje=cuerpo["id_mensaje"]
                )
            except httpx.HTTPStatusError as exc:
                # 503: el broker no está conectado a MQTT; no publicó nada.
                causa = f"el broker respondió HTTP {exc.response.status_code}: {exc.response.text[:200]}"
            except httpx.HTTPError as exc:
                causa = f"sin respuesta del broker ({type(exc).__name__})"
            except (ValueError, KeyError) as exc:
                causa = f"respuesta inválida del broker ({type(exc).__name__})"
            logger.error("Aviso OTA no publicado a %s: %s", aviso.get("serial"), causa)
            return ResultadoAvisoOta(publicado=False, mensaje=f"El broker no publicó ota/notify. Causa: {causa}.")


class UrlDescargaHmacAdapter(UrlDescargaPort):

    def __init__(self) -> None:
        self._secreto = os.environ.get("OTA_URL_SECRET", "").encode("utf-8")
        # URL pública con la que el nodo llega al backend (incluye /api detrás del proxy).
        self._base = os.environ.get("OTA_URL_BASE", "").rstrip("/")

    def configurada(self) -> bool:
        return bool(self._secreto and self._base)

    def _firmar(self, id_despliegue: int, expira_epoch: int) -> str:
        mensaje = f"{id_despliegue}:{expira_epoch}".encode("utf-8")
        return hmac.new(self._secreto, mensaje, hashlib.sha256).hexdigest()

    def generar(self, id_despliegue: int, expira: datetime) -> str:
        expira_epoch = int(expira.timestamp())
        consulta = urlencode({"expira": expira_epoch, "firma": self._firmar(id_despliegue, expira_epoch)})
        return f"{self._base}/prediccion/ota/artefactos/{id_despliegue}?{consulta}"

    def es_valida(self, id_despliegue: int, expira_epoch: int, firma: str, ahora: datetime) -> bool:
        if not self._secreto or expira_epoch < int(ahora.timestamp()):
            return False
        return hmac.compare_digest(self._firmar(id_despliegue, expira_epoch), firma)

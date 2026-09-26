"""Adaptador real de ``MqttPort`` -- llama a BROKER-MQTT-SGPMP por HTTP (RF-23).

El broker publica el comando en MQTT y espera hasta ~30s el ACK del
dispositivo antes de responder. Este adaptador nunca lanza: si la llamada
falla (broker caído, timeout de red, error HTTP) degrada a "PENDIENTE",
mismo espíritu que ``src/shared/firebase.py`` -- la fila ya quedó persistida
como PENDIENTE antes de llamar acá, así que un broker inalcanzable no debe
romper el flujo de negocio.
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading

import httpx
from sqlalchemy import text

from src.configuration.domain.repositories.mqtt_port import MqttPort, ResultadoEnvioMqtt

logger = logging.getLogger(__name__)


def verificar_token_configurado() -> None:
    """Chequeo de solo lectura al arranque: avisa si ``MQTT_BROKER_TOKEN`` quedó
    desincronizado del hash activo en ``modulo1.credenciales_servicio``.

    Nunca escribe nada — rotar el token sigue siendo una acción manual y
    deliberada (ver ``anotaciones/modulo_9/cu08_gaps_bd_rf23_mqtt.md``): que el
    proceso auto-corrija la BD en cada boot dejaría que un `.env` con un
    placeholder viejo pise en silencio una credencial que sí funcionaba, sin
    ningún rastro de quién lo hizo. Esto solo deja una advertencia en logs para
    detectar el desface temprano, en vez de recién al primer 401 del broker.
    """
    token = os.environ.get("MQTT_BROKER_TOKEN", "")
    if not token:
        return  # integración MQTT opcional -- sin token no hay nada que verificar

    from src.shared.database import SessionLocal

    hash_actual = hashlib.sha256(token.encode("utf-8")).hexdigest()
    db = SessionLocal()
    try:
        fila = db.execute(
            text(
                "SELECT hash_valor FROM modulo1.credenciales_servicio "
                "WHERE nombre_servicio = 'broker_mqtt' AND es_activo = true"
            )
        ).first()
    except Exception:
        logger.warning("No se pudo verificar MQTT_BROKER_TOKEN contra la BD al arrancar.", exc_info=True)
        return
    finally:
        db.close()

    if fila is None:
        logger.warning(
            "MQTT_BROKER_TOKEN está configurado pero no hay credencial activa "
            "'broker_mqtt' en modulo1.credenciales_servicio -- el broker va a "
            "rechazar todas las llamadas hasta que se registre una."
        )
    elif fila[0] != hash_actual:
        logger.warning(
            "MQTT_BROKER_TOKEN no coincide con el hash activo de 'broker_mqtt' en "
            "modulo1.credenciales_servicio. El backend no va a poder autenticarse "
            "contra BROKER-MQTT-SGPMP hasta corregir el .env o rotar la credencial."
        )

# ponytail: cap de concurrencia global -- este endpoint es sincrono (Session,
# no AsyncSession) y una espera de hasta ~35s ocupa un hilo del threadpool
# compartido de Starlette, usado por *todos* los endpoints del proceso. El
# cap evita que varias configuraciones concurrentes agoten ese pool y
# degraden endpoints no relacionados. Si este endpoint se vuelve de alto
# trafico, la solucion real es mover el router a async def/AsyncSession, no
# aplica para esta entrega.
_semaforo_llamadas_broker = threading.Semaphore(10)

# Timeout HTTP hacia el broker. Debe ser > que el timeout de ACK del broker
# (MQTT_ACK_TIMEOUT_SECONDS=30s en BROKER-MQTT-SGPMP) para dar margen a que el
# broker responda su veredicto NO_CONF en vez de que corte primero la red.
# Configurable por si el contrato de 30s cambia.
_TIMEOUT_HTTP_SEGUNDOS = float(os.environ.get("MQTT_BROKER_HTTP_TIMEOUT", "35"))
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

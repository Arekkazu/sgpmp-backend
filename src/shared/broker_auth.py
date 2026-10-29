"""Autenticación máquina-a-máquina del broker MQTT ante el backend (D3, P3 de AIOT-DEV-03).

Los endpoints ``/iot/*`` de dispositivo no los llama el nodo sino el broker
(``BROKER-MQTT-SGPMP``), que ya autenticó al nodo por MQTT (credencial por
Gateway Edge + ACL por serial). El serial deja de ser credencial: viaja en el
cuerpo como identidad del nodo y el broker se autentica con un token de
servicio en ``Authorization: Bearer``.

El token vive en la variable de entorno ``BROKER_SERVICE_TOKEN`` en los dos
lados (backend y broker) y se entrega por canal seguro, nunca en el repositorio.
Es distinto de ``MQTT_BROKER_TOKEN``, que es el del sentido contrario
(backend → broker). Mismo patrón que ``agrofusion_auth.py``: 503 si no está
configurado en el despliegue, 401 si no coincide.
"""
import os
import secrets
from typing import Optional

from fastapi import Header

from src.shared.errors import AuthenticationError, ServiceUnavailableError

_PREFIJO = "Bearer "


def require_token_servicio_broker(authorization: Optional[str] = Header(default=None)) -> None:
    """Dependencia FastAPI: exige el token de servicio del broker.

    Raises:
        ServiceUnavailableError: ``BROKER_SERVICE_TOKEN`` no está configurado. HTTP 503.
        AuthenticationError: falta el header o el token no coincide. HTTP 401.
    """
    esperado = os.getenv("BROKER_SERVICE_TOKEN", "")
    if not esperado:
        raise ServiceUnavailableError(
            code="TOKEN_SERVICIO_NO_CONFIGURADO",
            message="La integración con el broker MQTT no está disponible en este despliegue.",
        )
    if not authorization or not authorization.startswith(_PREFIJO):
        raise AuthenticationError(
            code="TOKEN_SERVICIO_INVALIDO",
            message="Se requiere el token de servicio del broker.",
        )
    # En bytes: compare_digest con str lanza TypeError ante caracteres no ASCII.
    recibido = authorization.removeprefix(_PREFIJO).encode("utf-8")
    if not secrets.compare_digest(recibido, esperado.encode("utf-8")):
        raise AuthenticationError(
            code="TOKEN_SERVICIO_INVALIDO",
            message="El token de servicio del broker no es válido.",
        )

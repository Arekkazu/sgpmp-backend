"""Autenticación máquina-a-máquina para la integración con el Hub de AgroFusion.

Distinta de ``rbac.py``/``get_current_user``: quien llama a
``/integraciones/agrofusion/*`` no es un ``Usuario`` de sgpmp con `id_rol`,
sino el Hub de AgroFusion autenticándose con un secreto de plataforma
compartido. Sigue el mismo patrón de configuración que el resto de
``src/shared/``: variables de entorno leídas con ``os.getenv`` a nivel de
módulo, sin objeto ``Settings`` centralizado.
"""
import os
import secrets

from dotenv import load_dotenv

from src.shared.errors import AuthenticationError, ServiceUnavailableError

load_dotenv()

_CLIENT_ID = os.getenv("AGROFUSION_HUB_CLIENT_ID")
_CLIENT_SECRET = os.getenv("AGROFUSION_HUB_CLIENT_SECRET")


def agrofusion_configurado() -> bool:
    """Indica si las credenciales M2M de AgroFusion están configuradas."""
    return bool(_CLIENT_ID and _CLIENT_SECRET)


def verify_agrofusion_client(client_id: str, client_secret: str) -> None:
    """Verifica las credenciales M2M que envía el Hub de AgroFusion.

    Se llama explícitamente al inicio de cada endpoint de
    ``/integraciones/agrofusion/*`` (no es una dependencia FastAPI estilo
    ``require_permission``, porque las credenciales viajan en query params en
    los `GET` y en el body en `POST`/`PATCH`, replicando el contrato real de
    ``backendint`` documentado en ``anotaciones/modulo_1/plan_sso_agrofusion.md``).

    Args:
        client_id: Identificador de cliente recibido en la petición.
        client_secret: Secreto de cliente recibido en la petición.

    Raises:
        ServiceUnavailableError: La integración M2M no está configurada en
            este despliegue. HTTP 503.
        AuthenticationError: Las credenciales no coinciden. HTTP 401.
    """
    if not agrofusion_configurado():
        raise ServiceUnavailableError(
            code="AGROFUSION_NO_CONFIGURADO",
            message="La integración server-to-server con AgroFusion no está disponible en este despliegue.",
        )

    valido = secrets.compare_digest(client_id, _CLIENT_ID) and secrets.compare_digest(
        client_secret, _CLIENT_SECRET
    )
    if not valido:
        raise AuthenticationError(
            code="CREDENCIALES_M2M_INVALIDAS",
            message="Las credenciales client_id/client_secret no son válidas.",
        )

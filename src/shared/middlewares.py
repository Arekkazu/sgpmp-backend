"""Middlewares globales de la aplicación FastAPI.

- `RequestContextMiddleware`: inyecta `request_id`, IP y user-agent en `request.state`
  y expone el correlativo como cabecera `X-Request-ID` en la respuesta.
- `AccessLogMiddleware`: registra método, ruta, código de respuesta y latencia.
- `setup_middlewares`: función de configuración que registra ambos middlewares.
  El CORS real está en `main.py` (con `allow_credentials=True` + orígenes
  explícitos, requerido por la cookie de refresh token); este módulo no
  declara CORS propio para evitar dos configuraciones divergentes.
"""
import uuid
import time
import logging
from typing import Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from src.shared import audit_context

log = logging.getLogger(__name__)

def _get_client_ip(request: Request) -> Optional[str]:
    """Extrae la IP real del cliente respetando la cabecera X-Forwarded-For.

    Args:
        request: Request FastAPI entrante.

    Returns:
        IP del cliente como string, o `None` si no está disponible.
    """
    # Respeta X-Forwarded-For si estás detrás de un proxy / LB
    xff = request.headers.get("x-forwarded-for")
    if xff:
        # Formato “client, proxy1, proxy2…”
        return xff.split(",")[0].strip()
    return request.client.host if request.client else None


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Inyecta request_id, ip, user_agent en request.state y
    los expone como X-Request-ID en la respuesta.
    """
    async def dispatch(self, request: Request, call_next):
        try:
            request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
            request.state.request_id = request_id
            request.state.ip = _get_client_ip(request)
            request.state.user_agent = request.headers.get("user-agent")
        except Exception:
            # Nunca bloquees la request por el contexto
            request.state.request_id = str(uuid.uuid4())
            request.state.ip = None
            request.state.user_agent = None

        # RF-10: deja el origen disponible para el repositorio de auditoría sin
        # que cada caso de uso tenga que arrastrarlo. Abrir el contexto aquí
        # también evita que un request herede el del anterior si comparten hilo.
        audit_context.iniciar_request(
            ip=getattr(request.state, "ip", None),
            user_agent=getattr(request.state, "user_agent", None),
        )

        response = await call_next(request)
        # Propaga el correlativo a la respuesta
        try:
            response.headers["X-Request-ID"] = request.state.request_id
        except Exception:
            pass
        return response


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Logging simple de acceso (útil si no dependes solo del log de Uvicorn)."""
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        req_id = getattr(request.state, "request_id", "-")
        log.info("Request [%s] %s %s", req_id, request.method, request.url.path)
        response = await call_next(request)
        elapsed = (time.time() - start) * 1000
        log.info("Response [%s] %s %s %d (%.1fms)",
                req_id, request.method, request.url.path, response.status_code, elapsed)
        return response


def setup_middlewares(app):
    """Agrega los middlewares a la aplicación FastAPI."""
    # Orden recomendado: primero contexto, luego logs
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(AccessLogMiddleware)
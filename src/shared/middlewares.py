import uuid
import time
import logging
from typing import Optional
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

log = logging.getLogger(__name__)

def _get_client_ip(request: Request) -> Optional[str]:
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
    # CORS (mantén X-Request-ID permitido)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],            # TODO: restringir en prod
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],   # para que el frontend pueda leerlo
    )

    # Orden recomendado: primero contexto, luego logs
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(AccessLogMiddleware)
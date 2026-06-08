"""Handler global unico para el arbol de errores de dominio (shared.errors).

Se registra en app/main.py con register_error_handlers(app). Solo se dispara
para excepciones AppError, que lanza el codigo de la nueva arquitectura; el
codigo antiguo (que lanza HTTPException) sigue funcionando igual. Asi conviven
ambas estructuras durante la migracion.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .errors import AppError, InfrastructureError, ServiceUnavailableError

logger = logging.getLogger(__name__)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handler para toda la jerarquía `AppError`.

    Registra en log los errores de infraestructura e incluye `error_code`,
    `message`, `fields` y `timestamp` en el cuerpo JSON de la respuesta.

    Args:
        request: Request FastAPI que originó el error.
        exc: Instancia de `AppError` o cualquier subclase.

    Returns:
        JSONResponse con el código HTTP y cuerpo estándar de error.
    """
    if isinstance(exc, (InfrastructureError, ServiceUnavailableError)) and exc.original_error is not None:
        logger.error(
            "%s [%s] en %s: %r",
            type(exc).__name__,
            exc.code,
            request.url,
            exc.original_error,
        )

    fields = [{"field": exc.field, "message": exc.message}] if exc.field else []

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.code,
            "message": exc.message,
            "fields": fields,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


async def request_validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handler para errores de validación de Pydantic en el request body o parámetros.

    Convierte la lista de errores de Pydantic al formato estándar `fields`.

    Args:
        request: Request FastAPI que originó el error.
        exc: Excepción `RequestValidationError` de FastAPI.

    Returns:
        JSONResponse 400 con los campos que fallaron la validación.
    """
    fields = []
    for error in exc.errors():
        loc = error.get("loc", ())
        field = ".".join(str(l) for l in loc[1:]) if len(loc) > 1 else None
        fields.append({"field": field, "message": error.get("msg", "Error de validacion")})

    return JSONResponse(
        status_code=400,
        content={
            "error_code": "VAL_ENTRADA",
            "message": "Errores de validacion en la solicitud",
            "fields": fields,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


def register_error_handlers(app) -> None:
    """Registra los handlers de errores en la app FastAPI."""
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)

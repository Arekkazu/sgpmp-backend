"""Handlers globales de error de la aplicación FastAPI.

Se registran en main.py con register_error_handlers(app). Cubren tres capas:

- `AppError` y subclases: los errores que lanza el código de la nueva
  arquitectura. El codigo antiguo (que lanza HTTPException) sigue funcionando
  igual, asi conviven ambas estructuras durante la migracion.
- `RequestValidationError`: los fallos de validación de Pydantic.
- Red de seguridad: `OperationalError`/`InterfaceError` de SQLAlchemy salen como
  `503`, y cualquier otra excepción no controlada como `500`. Sin estos dos
  últimos, un fallo de base de datos a mitad de request escapa a Starlette y
  sale como `Internal Server Error` en texto plano, con una forma distinta al
  resto de la API (INC-M01-06-024).

Todos emiten el mismo cuerpo, el que documenta `ErrorResponse` en `schemas.py`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import InterfaceError, OperationalError, SQLAlchemyError

from .errors import AppError, GatewayTimeoutError, InfrastructureError, ServiceUnavailableError

logger = logging.getLogger(__name__)


def _respuesta_error(
    status_code: int,
    code: str,
    message: str,
    fields: list[dict] | None = None,
) -> JSONResponse:
    """Construye el cuerpo estándar de error.

    Args:
        status_code: Código HTTP de la respuesta.
        code: Código de negocio en mayúsculas.
        message: Mensaje legible para el usuario final.
        fields: Detalle por campo. Lista vacía si el error no aplica a uno.

    Returns:
        JSONResponse con las claves `error_code`, `message`, `fields` y `timestamp`.
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "error_code": code,
            "message": message,
            "fields": fields or [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


def _request_id(request: Request) -> str:
    """Devuelve el correlativo que puso `RequestContextMiddleware`, o `-`."""
    return getattr(request.state, "request_id", "-")


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
    if (
        isinstance(exc, (InfrastructureError, ServiceUnavailableError, GatewayTimeoutError))
        and exc.original_error is not None
    ):
        logger.error(
            "%s [%s] en %s: %r",
            type(exc).__name__,
            exc.code,
            request.url,
            exc.original_error,
        )

    fields = [{"field": exc.field, "message": exc.message}] if exc.field else []

    return _respuesta_error(exc.status_code, exc.code, exc.message, fields)


def _usuario_del_token(request: Request) -> int | None:
    """Extrae `id_usuario` del Bearer token, sin lanzar si no es válido.

    Un `RequestValidationError` de body solo puede ocurrir después de que
    `get_current_user` ya resolvió el token exitosamente (FastAPI resuelve
    las sub-dependencias del endpoint antes que el body) — así que en la
    práctica esto siempre decodifica un token válido. Se revalida aquí en
    vez de leer `request.state` porque `get_current_user` no publica nada
    ahí; si algo cambia esa garantía, el peor caso es no poder identificar
    al usuario responsable del evento de auditoría, nunca un 500.
    """
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        return None
    try:
        from src.shared.jwt import verify_token

        payload = verify_token(authorization.removeprefix("Bearer "))
        return int(payload["sub"])
    except Exception:
        return None


def _auditar_validacion_rechazada_m02(request: Request, fields: list[dict]) -> None:
    """RF-36/RF-52: deja constancia en `bitacora_auditoria_m02` de un 400 rechazado.

    Solo aplica a `/activos-biologicos` — el resto de módulos no comparte esa
    bitácora. Nunca debe hacer fallar la respuesta 400 que ya se le va a dar
    al cliente: cualquier error aquí se traga en silencio.
    """
    if not request.url.path.startswith("/activos-biologicos"):
        return

    from src.biological_assets.domain.entities.activo_biologico import EventoAuditoria
    from src.biological_assets.infrastructure.repositories.bitacora_auditoria_repository import (
        SqlAlchemyBitacoraAuditoriaRepository,
    )
    from src.shared.database import SessionLocal

    id_activo_raw = request.path_params.get("id_activo")
    try:
        id_activo = int(id_activo_raw) if id_activo_raw is not None else None
    except (TypeError, ValueError):
        id_activo = None

    db = SessionLocal()
    try:
        SqlAlchemyBitacoraAuditoriaRepository(db).registrar(EventoAuditoria(
            rf_origen="RF36",
            tipo_evento="VALIDACION_RECHAZADA",
            clasificacion_biologica="GESTION_OPERATIVA",
            resultado="FALLIDO",
            severidad_log="WARNING",
            timestamp_evento=datetime.now(timezone.utc),
            id_activo_biologico=id_activo,
            descripcion=f"{request.method} {request.url.path} rechazado por validación de entrada (400)",
            detalle_tecnico={"fields": fields},
            id_usuario_responsable=_usuario_del_token(request),
        ))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


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

    # INC-M02-43-G29 / RF-36: las operaciones rechazadas antes de llegar al
    # use case (400 de Pydantic) también deben quedar en la bitácora de M02.
    _auditar_validacion_rechazada_m02(request, fields)

    return _respuesta_error(400, "VAL_ENTRADA", "Errores de validacion en la solicitud", fields)


async def db_no_disponible_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handler para fallos de conectividad con la base de datos (HTTP 503).

    Cubre la conexión que se cae *a mitad* del request; la que falla al tomarse
    la traduce antes `get_db` en `src/shared/database.py`.

    Args:
        request: Request FastAPI que originó el error.
        exc: `OperationalError` o `InterfaceError` de SQLAlchemy.

    Returns:
        JSONResponse 503 con código `BD_NO_DISPONIBLE`.
    """
    logger.error(
        "Base de datos no disponible en %s [%s]: %r", request.url, _request_id(request), exc
    )
    return _respuesta_error(
        503,
        "BD_NO_DISPONIBLE",
        "El servicio no está disponible temporalmente. Intenta de nuevo en unos momentos.",
    )


async def error_no_controlado_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handler de último recurso para cualquier excepción no prevista (HTTP 500).

    El detalle de la excepción va solo al log: el cliente recibe un mensaje
    genérico y el correlativo con el que se puede rastrear el fallo.

    Args:
        request: Request FastAPI que originó el error.
        exc: Cualquier excepción no cubierta por los handlers anteriores.

    Returns:
        JSONResponse 500 con código `ERROR_INTERNO`.
    """
    logger.exception("Error no controlado en %s [%s]", request.url, _request_id(request))
    # El correlativo va en la cabecera X-Request-ID, no en el cuerpo: el
    # frontend no lee cabeceras, así que el mensaje no se lo promete al usuario.
    return _respuesta_error(
        500,
        "ERROR_INTERNO",
        "Ocurrió un error interno. Intenta de nuevo; si el problema persiste, "
        "contacta al equipo de soporte.",
    )


def register_error_handlers(app) -> None:
    """Registra los handlers de errores en la aplicación FastAPI.

    El orden no importa: Starlette resuelve por MRO, así que `OperationalError`
    (subclase de `SQLAlchemyError`) gana sobre el handler genérico.
    """
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.add_exception_handler(OperationalError, db_no_disponible_handler)
    app.add_exception_handler(InterfaceError, db_no_disponible_handler)
    app.add_exception_handler(SQLAlchemyError, error_no_controlado_handler)
    app.add_exception_handler(Exception, error_no_controlado_handler)

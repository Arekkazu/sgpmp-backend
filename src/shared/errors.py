"""Jerarquia de errores de dominio compartida (shared.errors).

Los adaptadores de infraestructura (repositorios SQLAlchemy, clientes SMTP,
HTTP, etc.) capturan su excepcion nativa y la convierten en una de estas.
Un unico handler global (ver error_handlers.py) las traduce a respuestas HTTP
estructuradas. El dominio solo conoce este arbol, nunca las excepciones del
framework.
"""
from __future__ import annotations

from typing import Optional


class AppError(Exception):
    """Error base de la aplicacion: code + message + field opcional.

    `status_code` es el HTTP que el handler global devuelve para este tipo.
    """

    status_code: int = 400

    def __init__(self, code: str, message: str, field: Optional[str] = None):
        self.code = code
        self.message = message
        self.field = field
        super().__init__(message)


class ValidationError(AppError):
    """Datos de entrada invalidos a nivel de regla de dominio."""

    status_code = 400


class ConflictError(AppError):
    """Conflicto con el estado actual (p. ej. recurso duplicado)."""

    status_code = 409


class BusinessRuleError(AppError):
    """Violacion de una regla de negocio."""

    status_code = 422


class FlowError(AppError):
    """Fallo ocurrido durante la ejecucion de un proceso de varias etapas.

    Se diferencia de BusinessRuleError en que el problema no es una precondicion
    sino un fallo a mitad del flujo: token expirado/usado, rollback de plantilla,
    batch interrumpido, transicion fuera de secuencia.
    """

    status_code = 422


class NotFoundError(AppError):
    """El recurso solicitado no existe."""

    status_code = 404


class AuthenticationError(AppError):
    """El actor no pudo ser autenticado (credenciales invalidas, sesion)."""

    status_code = 401


class AuthorizationError(AppError):
    """El actor esta autenticado pero no tiene permiso para la operacion."""

    status_code = 403


class GoneError(AppError):
    """El recurso existio pero ya no esta disponible (token expirado/usado)."""

    status_code = 410


class InfrastructureError(AppError):
    """Fallo de un adaptador externo (DB, SMTP, HTTP...).

    Conserva la excepcion original para el log; nunca se expone al cliente.
    """

    status_code = 500

    def __init__(
        self,
        code: str,
        message: str,
        original_error: Optional[BaseException] = None,
        field: Optional[str] = None,
    ):
        super().__init__(code, message, field)
        self.original_error = original_error


class ServiceUnavailableError(AppError):
    """Servicio externo no disponible temporalmente (SMTP, terceros).

    Conserva la excepcion original para el log; nunca se expone al cliente.
    """

    status_code = 503

    def __init__(
        self,
        code: str,
        message: str,
        original_error: Optional[BaseException] = None,
        field: Optional[str] = None,
    ):
        super().__init__(code, message, field)
        self.original_error = original_error

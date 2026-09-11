"""Jerarquía de errores de dominio compartida.

Todos los errores de negocio e infraestructura heredan de ``AppError``.
Los adaptadores de infraestructura (repositorios SQLAlchemy, clientes SMTP,
HTTP, etc.) capturan su excepción nativa y la convierten en una de estas
clases. Un único handler global (``error_handlers.py``) las traduce a
respuestas HTTP estructuradas. El dominio solo conoce este árbol, nunca
las excepciones del framework.

Jerarquía de uso::

    AppError
    ├── ValidationError        400  Dato inválido a nivel de regla de dominio
    ├── AuthenticationError    401  Credenciales inválidas o JWT ausente/expirado
    ├── AuthorizationError     403  Autenticado pero sin permiso para la operación
    ├── NotFoundError          404  Recurso no existe
    ├── GoneError              410  Recurso que existió pero ya no aplica
    ├── PreconditionFailedError 412 Conflicto de concurrencia optimista
    ├── ConflictError          409  Recurso duplicado
    ├── BusinessRuleError      422  Violación de regla de negocio
    ├── FlowError              422  Fallo a mitad de un proceso de varias etapas
    ├── LockedError            423  Recurso bloqueado temporalmente
    ├── TooManyRequestsError   429  Límite de concurrencia u operaciones simultáneas excedido
    ├── InfrastructureError    500  Fallo de adaptador externo
    ├── ServiceUnavailableError 503 Servicio externo no disponible temporalmente
    └── GatewayTimeoutError    504  Servicio externo no confirmó a tiempo (timeout de ACK)
"""
from __future__ import annotations

from typing import Optional


class AppError(Exception):
    """Error base de la aplicación.

    Todos los errores de dominio e infraestructura heredan de esta clase.
    Lleva un ``code`` de negocio legible por máquina, un ``message`` legible
    por humanos y un ``field`` opcional que identifica el campo que originó
    el error.

    Attributes:
        status_code: Código HTTP que el handler global devuelve para este tipo.
        code: Código de negocio en mayúsculas (ej: ``USUARIO_NO_ENCONTRADO``).
        message: Mensaje descriptivo para el cliente.
        field: Nombre del campo que causó el error, si aplica.
    """

    status_code: int = 400

    def __init__(self, code: str, message: str, field: Optional[str] = None):
        """Inicializa el error con código, mensaje y campo opcional.

        Args:
            code: Código de negocio en mayúsculas (ej: ``CORREO_DUPLICADO``).
            message: Mensaje legible para el usuario final.
            field: Nombre del campo que originó el error. ``None`` si el error
                no está asociado a un campo específico.
        """
        self.code = code
        self.message = message
        self.field = field
        super().__init__(message)


class ValidationError(AppError):
    """Dato de entrada inválido a nivel de regla de dominio (HTTP 400).

    Usar cuando un valor no cumple una restricción de negocio verificada
    en el use case, no en Pydantic. Ejemplo: contraseña que no supera la
    política de seguridad, fecha de nacimiento futura.
    """

    status_code = 400


class ConflictError(AppError):
    """Conflicto con el estado actual del recurso (HTTP 409).

    Usar cuando se intenta crear un recurso que ya existe o una operación
    viola una restricción de unicidad. Ejemplo: correo electrónico duplicado,
    nombre de rol ya registrado.
    """

    status_code = 409


class BusinessRuleError(AppError):
    """Violación de una regla de negocio (HTTP 422).

    Usar cuando la operación es estructuralmente válida pero viola una
    invariante del dominio. Ejemplo: intentar eliminar el último administrador
    activo, transición de estado no permitida.
    """

    status_code = 422


class FlowError(AppError):
    """Fallo ocurrido a mitad de un proceso de varias etapas (HTTP 422).

    Se diferencia de ``BusinessRuleError`` en que el problema no es una
    precondición de negocio sino un fallo durante la ejecución del flujo.
    Ejemplo: token de activación ya usado, transición fuera de secuencia,
    batch interrumpido.
    """

    status_code = 422


class NotFoundError(AppError):
    """El recurso solicitado no existe (HTTP 404)."""

    status_code = 404


class AuthenticationError(AppError):
    """El actor no pudo ser autenticado (HTTP 401).

    Usar cuando las credenciales son inválidas, el JWT está ausente,
    expirado o fue revocado.
    """

    status_code = 401


class AuthorizationError(AppError):
    """El actor está autenticado pero no tiene permiso para la operación (HTTP 403).

    Usar cuando la identidad del usuario es válida pero su rol o permisos
    no le permiten ejecutar la acción solicitada.
    """

    status_code = 403


class MethodNotAllowedError(AppError):
    """El método HTTP no está permitido sobre el recurso (HTTP 405).

    Usar cuando el recurso existe pero la operación está prohibida por diseño,
    no por falta de permisos. Caso de referencia: los registros de auditoría de
    RF-10, inmutables tanto a nivel de API como de base de datos.
    """

    status_code = 405


class GoneError(AppError):
    """El recurso existió pero ya no está disponible (HTTP 410).

    Usar para recursos con ciclo de vida explícito que han expirado o sido
    consumidos. Ejemplo: token de activación expirado, enlace de recuperación
    ya utilizado.
    """

    status_code = 410


class InfrastructureError(AppError):
    """Fallo de un adaptador externo (HTTP 500).

    Usar cuando una dependencia de infraestructura (DB, SMTP, API externa)
    falla de forma inesperada. Conserva la excepción original para el log;
    nunca se expone al cliente.

    Attributes:
        original_error: Excepción original capturada del adaptador.
    """

    status_code = 500

    def __init__(
        self,
        code: str,
        message: str,
        original_error: Optional[BaseException] = None,
        field: Optional[str] = None,
    ):
        """Inicializa el error preservando la excepción de infraestructura.

        Args:
            code: Código de negocio en mayúsculas.
            message: Mensaje legible para el usuario final.
            original_error: Excepción original del adaptador, para logging.
            field: Nombre del campo relacionado, si aplica.
        """
        super().__init__(code, message, field)
        self.original_error = original_error


class GatewayTimeoutError(AppError):
    """Un servicio externo no confirmó la operación a tiempo (HTTP 504).

    Usar cuando el flujo depende de una confirmación asíncrona de un
    dispositivo/servicio de terceros (ej: ACK de un dispositivo IoT vía
    MQTT) y el plazo de espera se agota sin respuesta. Distinto de
    ``ServiceUnavailableError``: acá el servicio externo respondió (o el
    comando se envió con éxito), solo que la confirmación no llegó a tiempo.

    Attributes:
        original_error: Excepción original capturada del adaptador, si aplica.
    """

    status_code = 504

    def __init__(
        self,
        code: str,
        message: str,
        original_error: Optional[BaseException] = None,
        field: Optional[str] = None,
    ):
        super().__init__(code, message, field)
        self.original_error = original_error


class LockedError(AppError):
    """Recurso bloqueado temporalmente (HTTP 423).

    Usar cuando el acceso al recurso está suspendido por un tiempo determinado.
    Ejemplo: cuenta bloqueada por exceso de intentos de login fallidos.
    """

    status_code = 423


class PreconditionFailedError(AppError):
    """Conflicto de concurrencia optimista (HTTP 412).

    Usar cuando el recurso fue modificado por otro actor entre la lectura y
    la escritura del cliente actual. Requiere que el cliente obtenga la
    versión actualizada antes de reintentar.
    """

    status_code = 412


class TooManyRequestsError(AppError):
    """Límite de concurrencia u operaciones simultáneas excedido (HTTP 429).

    Usar cuando el sistema rechaza una operación porque ya hay demasiados
    trabajos en curso del mismo tipo (ej: generación de reportes,
    exportaciones). El cliente debe reintentar más tarde.
    """

    status_code = 429


class ServiceUnavailableError(AppError):
    """Servicio externo no disponible temporalmente (HTTP 503).

    Usar cuando un servicio de terceros (SMTP, Firebase, API externa) no
    responde después de agotar los reintentos. Conserva la excepción original
    para el log; nunca se expone al cliente.

    Attributes:
        original_error: Excepción original capturada del servicio externo.
    """

    status_code = 503

    def __init__(
        self,
        code: str,
        message: str,
        original_error: Optional[BaseException] = None,
        field: Optional[str] = None,
    ):
        """Inicializa el error preservando la excepción del servicio externo.

        Args:
            code: Código de negocio en mayúsculas.
            message: Mensaje legible para el usuario final.
            original_error: Excepción original del servicio externo, para logging.
            field: Nombre del campo relacionado, si aplica.
        """
        super().__init__(code, message, field)
        self.original_error = original_error

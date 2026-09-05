"""Enumeraciones de dominio compartidas entre modelos ORM y DTOs.

Todas heredan de `str` para ser serializables directamente a JSON y
compatibles con los valores almacenados en las columnas ENUM de PostgreSQL.
"""
import enum

class EnumAccionCuenta(str, enum.Enum):
    """Acciones administrativas aplicables sobre una cuenta de usuario."""
    ACTIVAR = 'activar'
    INACTIVAR = 'inactivar'
    ELIMINAR = 'eliminar'
    BLOQUEAR = 'bloquear'
    PENDIENTE = 'pendiente'


class EnumEstadoEnvio(str, enum.Enum):
    """Estado de envío de una notificación."""
    EN_COLA = 'en_cola'
    ENVIADO = 'enviado'
    FALLIDO = 'fallido'


class EnumEventoResultado(str, enum.Enum):
    """Resultado de un evento de auditoría."""
    EXITOSO = 'exitoso'
    FALLIDO = 'fallido'


class EnumTokenTipo(str, enum.Enum):
    """Tipo de token almacenado en la tabla `tokens`."""
    RECUPERACION = 'recuperacion'
    VERIFICACION_CORREO = 'verificacion_correo'
    ACCESO = 'acceso'
    REFRESCO = 'refresco'


class EnumUsuarioGenero(str, enum.Enum):
    """Género del usuario según catálogo del sistema."""
    M = 'M'
    X = 'X'
    F = 'F'
    T = 'T'
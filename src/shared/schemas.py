"""Schemas de respuesta HTTP compartidos por todos los módulos.

Define los modelos Pydantic que estandarizan las respuestas de éxito y error
de todos los endpoints. Son usados como ``response_model`` en los decoradores
de ruta y en las respuestas de error del handler global.
"""
from typing import Optional

from pydantic import BaseModel


class MessageResponse(BaseModel):
    """Respuesta estándar para operaciones que retornan solo un mensaje.

    Attributes:
        message: Mensaje descriptivo del resultado de la operación.
    """

    message: str


class FieldError(BaseModel):
    """Detalle de un error asociado a un campo específico del request.

    Attributes:
        field: Nombre del campo que originó el error. ``None`` si el error
            no está asociado a un campo específico.
        message: Descripción del error para ese campo.
    """

    field: Optional[str] = None
    message: str


class ErrorResponse(BaseModel):
    """Respuesta estándar para todos los errores del sistema.

    Estructura unificada que retorna el handler global para cualquier
    ``AppError``. El cliente siempre recibe este formato independientemente
    del tipo de error.

    Attributes:
        error_code: Código de negocio en mayúsculas (ej: ``USUARIO_NO_ENCONTRADO``).
        message: Mensaje legible para el usuario final.
        fields: Lista de errores por campo. Vacía si el error no es de validación.
        timestamp: Marca temporal ISO 8601 del momento en que ocurrió el error.
    """

    error_code: str
    message: str
    fields: list[FieldError]
    timestamp: str

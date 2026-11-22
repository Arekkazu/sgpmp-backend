# | Fecha      | Nombre         | Que se hizo |
# |------------|----------------|-------------|
# | 2026-11-19 | LuisfNarvaez01 | TC-M07-381 RF-97: detalle opcional en ErrorResponse |
# | 2026-11-19 | Arekkazu       | INC-M07-375-G002 RF-95: `field` en el cuerpo de error |
"""Schemas de respuesta HTTP compartidos por todos los módulos.

Define los modelos Pydantic que estandarizan las respuestas de éxito y error
de todos los endpoints. Son usados como ``response_model`` en los decoradores
de ruta y en las respuestas de error del handler global.
"""
from decimal import Decimal
from typing import Annotated, Optional

from pydantic import BaseModel, PlainSerializer

#: Decimal que viaja como número JSON. Pydantic v2 serializa ``Decimal`` como
#: texto (``"10.0000"``) y el cliente lo declara ``number``: con texto, la
#: pantalla de calibración del frontend quedaba en blanco (#251). Solo para
#: medidas (calibración, rangos de sensor); los montos contables (NIC 41) se
#: quedan en ``Decimal`` porque ``float`` perdería precisión.
DecimalNumero = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]


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
        field: Primer campo que falló (``fields[0].field``), o ``null`` si el error no aplica a uno.
        fields: Lista de errores por campo. Vacía si el error no es de validación.
        timestamp: Marca temporal ISO 8601 del momento en que ocurrió el error.
        detalle: Datos estructurados del error; solo aparece cuando el error los trae.
    """

    error_code: str
    message: str
    field: Optional[str] = None
    fields: list[FieldError]
    timestamp: str
    detalle: Optional[dict] = None

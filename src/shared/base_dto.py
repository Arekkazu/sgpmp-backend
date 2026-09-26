"""DTO base compartido para todos los módulos del sistema.

Define la configuración Pydantic común que heredan todos los DTOs de entrada.
Centraliza comportamientos transversales para evitar duplicación entre módulos.
"""
from pydantic import BaseModel, ConfigDict, field_validator


def _contiene_byte_nulo(valor: object) -> bool:
    return isinstance(valor, str) and "\x00" in valor


class BaseDTO(BaseModel):
    """Clase base para todos los DTOs de entrada del sistema.

    Aplica ``str_strip_whitespace=True`` de forma global: todos los campos
    de tipo ``str`` en los DTOs heredados tendrán sus espacios iniciales y
    finales eliminados automáticamente antes de cualquier validación.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
    )

    # INC-M02-57-G06: un byte nulo embebido en un campo de texto libre no lo
    # rechazaba ninguna validación de entrada; llegaba hasta psycopg2, que lo
    # rechaza con un ValueError de Python plano que el traductor de errores de
    # base de datos no reconocía, y salía como 500 en vez del 400 controlado
    # que exige un dato mal formado. Se rechaza aquí, en la frontera, para que
    # ningún campo de texto de ningún DTO del sistema llegue a la base de datos
    # con un byte nulo.
    @field_validator("*", mode="before")
    @classmethod
    def _rechazar_byte_nulo(cls, valor: object) -> object:
        tiene_byte_nulo = _contiene_byte_nulo(valor) or (
            isinstance(valor, list) and any(_contiene_byte_nulo(item) for item in valor)
        )
        if tiene_byte_nulo:
            raise ValueError("El texto no puede contener caracteres nulos.")
        return valor

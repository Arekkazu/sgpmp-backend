"""DTO base compartido para todos los módulos del sistema.

Define la configuración Pydantic común que heredan todos los DTOs de entrada.
Centraliza comportamientos transversales para evitar duplicación entre módulos.
"""
from pydantic import BaseModel, ConfigDict


class BaseDTO(BaseModel):
    """Clase base para todos los DTOs de entrada del sistema.

    Aplica ``str_strip_whitespace=True`` de forma global: todos los campos
    de tipo ``str`` en los DTOs heredados tendrán sus espacios iniciales y
    finales eliminados automáticamente antes de cualquier validación.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
    )

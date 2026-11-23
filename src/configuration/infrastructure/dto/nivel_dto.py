# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""DTO anidado: un nivel de alerta dentro de un umbral ambiental."""
from __future__ import annotations

from decimal import Decimal

from pydantic import field_validator

from src.shared.base_dto import BaseDTO

_NIVELES_VALIDOS = {'normal', 'precaucion', 'critico'}


class NivelDTO(BaseDTO):
    """Tramo de un nivel (``normal`` | ``precaucion`` | ``critico``) dentro del rango
    del umbral.
    """
    nivel: str
    limite_inferior: Decimal
    limite_superior: Decimal

    @field_validator('nivel')
    @classmethod
    def validar_nivel(cls, v: str) -> str:
        """Valida el nivel de alerta."""
        v = v.strip().lower()
        if v not in _NIVELES_VALIDOS:
            raise ValueError(f"El nivel debe ser uno de: {', '.join(sorted(_NIVELES_VALIDOS))}.")
        return v

    @field_validator('limite_superior')
    @classmethod
    def validar_limites(cls, v: Decimal, info) -> Decimal:
        """Exige que el límite superior sea mayor que el inferior."""
        inferior = info.data.get('limite_inferior')
        if inferior is not None and v <= inferior:
            raise ValueError("El limite_superior debe ser mayor que el limite_inferior.")
        return v

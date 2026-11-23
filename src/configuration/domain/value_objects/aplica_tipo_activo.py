# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Value object ``AplicaTipoActivo`` — scope de aplicación de una métrica."""
from __future__ import annotations

from enum import Enum

from src.shared.errors import ValidationError

_VALORES_VALIDOS = {'INDIVIDUAL', 'LOTE', 'AMBOS'}


class AplicaTipoActivo(str, Enum):
    """A qué tipo de activo aplica una métrica: individual, lote o ambos."""
    INDIVIDUAL = 'INDIVIDUAL'
    LOTE = 'LOTE'
    AMBOS = 'AMBOS'

    @classmethod
    def desde_string(cls, valor: str) -> 'AplicaTipoActivo':
        """Convierte el texto en el valor del catálogo.

        Raises:
            ValidationError: Si el valor no pertenece al catálogo.
        """
        normalizado = valor.strip().upper()
        try:
            return cls(normalizado)
        except ValueError:
            raise ValidationError(
                code="APLICA_TIPO_ACTIVO_INVALIDO",
                message=f"El valor de aplica_a_tipo_activo debe ser uno de: {', '.join(_VALORES_VALIDOS)}.",
                field="aplica_a_tipo_activo",
            )

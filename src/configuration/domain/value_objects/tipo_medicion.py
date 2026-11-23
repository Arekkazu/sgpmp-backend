# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Value object ``TipoMedicion`` — tipo de medición de una métrica de producción."""
from __future__ import annotations

from enum import Enum

from src.shared.errors import ValidationError

_VALORES_VALIDOS = {'PESO', 'VOLUMEN', 'LONGITUD', 'CONTEO', 'OTRO'}


class TipoMedicion(str, Enum):
    """Magnitud que mide una métrica de producción."""
    PESO = 'PESO'
    VOLUMEN = 'VOLUMEN'
    LONGITUD = 'LONGITUD'
    CONTEO = 'CONTEO'
    OTRO = 'OTRO'

    @classmethod
    def desde_string(cls, valor: str) -> 'TipoMedicion':
        """Convierte el texto en el valor del catálogo.

        Raises:
            ValidationError: Si el valor no pertenece al catálogo.
        """
        normalizado = valor.strip().upper()
        try:
            return cls(normalizado)
        except ValueError:
            raise ValidationError(
                code="TIPO_MEDICION_INVALIDO",
                message=f"El tipo de medición debe ser uno de: {', '.join(_VALORES_VALIDOS)}.",
                field="tipo_medicion",
            )

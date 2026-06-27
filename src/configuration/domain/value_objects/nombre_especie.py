"""Value object ``NombreEspecie`` del dominio de configuración.

Inmutable y comparado por valor. Valida longitud y formato en construcción,
de modo que en el resto del dominio es imposible tener un nombre inválido.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from src.shared.errors import ValidationError

# Solo letras (incluye tildes y ñ) y espacios simples. Sin dígitos ni símbolos.
_FORMATO_NOMBRE = re.compile(r"^[A-Za-zÁÉÍÓÚáéíóúÑñ][A-Za-zÁÉÍÓÚáéíóúÑñ ]*$")

_MIN = 3
_MAX = 50


@dataclass(frozen=True)
class NombreEspecie:
    """Nombre válido y normalizado de una especie productiva.

    Attributes:
        valor: Texto del nombre, sin espacios al inicio/fin.

    Raises:
        ValidationError: Si el nombre está vacío, fuera de rango o contiene
            caracteres no permitidos. HTTP 400.
    """

    valor: str

    def __post_init__(self) -> None:
        normalizado = self.valor.strip()
        if not normalizado:
            raise ValidationError(
                code="NOMBRE_ESPECIE_REQUERIDO",
                message="El nombre de la especie es obligatorio.",
                field="nombre",
            )
        if len(normalizado) < _MIN or len(normalizado) > _MAX:
            raise ValidationError(
                code="NOMBRE_ESPECIE_LONGITUD_INVALIDA",
                message=f"El nombre de la especie debe tener entre {_MIN} y {_MAX} caracteres.",
                field="nombre",
            )
        if not _FORMATO_NOMBRE.match(normalizado):
            raise ValidationError(
                code="NOMBRE_ESPECIE_FORMATO_INVALIDO",
                message="El nombre de la especie solo puede contener letras y espacios, sin símbolos ni números.",
                field="nombre",
            )
        object.__setattr__(self, "valor", normalizado)

    def normalizado(self) -> str:
        """Retorna el nombre en minúsculas para comparaciones case-insensitive."""
        return self.valor.lower()

    def __str__(self) -> str:
        return self.valor

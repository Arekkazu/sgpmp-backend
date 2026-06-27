"""Value object ``NombrePatologia`` — nombre de una patología del catálogo."""
from __future__ import annotations

import re
from dataclasses import dataclass

from src.shared.errors import ValidationError

# Permite letras, números, espacios, paréntesis, guiones y punto (nombres médicos).
_FORMATO = re.compile(r"^[A-Za-zÁÉÍÓÚáéíóúÑñ][A-Za-zÁÉÍÓÚáéíóúÑñ0-9 \-(). ]*$")

_MIN = 3
_MAX = 60  # límite de la columna en DB (varchar 60)


@dataclass(frozen=True)
class NombrePatologia:
    valor: str

    def __post_init__(self) -> None:
        v = self.valor.strip()
        if not v:
            raise ValidationError(
                code="NOMBRE_PATOLOGIA_REQUERIDO",
                message="El nombre de la patología es obligatorio.",
                field="nombre",
            )
        if len(v) < _MIN or len(v) > _MAX:
            raise ValidationError(
                code="NOMBRE_PATOLOGIA_LONGITUD_INVALIDA",
                message=f"El nombre de la patología debe tener entre {_MIN} y {_MAX} caracteres.",
                field="nombre",
            )
        if not _FORMATO.match(v):
            raise ValidationError(
                code="NOMBRE_PATOLOGIA_FORMATO_INVALIDO",
                message="El nombre de la patología contiene caracteres no permitidos.",
                field="nombre",
            )
        object.__setattr__(self, "valor", v)

    def normalizado(self) -> str:
        return self.valor.lower()

    def __str__(self) -> str:
        return self.valor

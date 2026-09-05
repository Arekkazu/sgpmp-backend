"""Value object ``NombreEtapa`` — nombre de una etapa del ciclo productivo."""
from __future__ import annotations

import re
from dataclasses import dataclass

from src.shared.errors import ValidationError

# Letras (con tildes y ñ), espacios, guiones y paréntesis.
_FORMATO = re.compile(r"^[A-Za-zÁÉÍÓÚáéíóúÑñ][A-Za-zÁÉÍÓÚáéíóúÑñ0-9 \-()]*$")

_MIN = 3
_MAX = 50


@dataclass(frozen=True)
class NombreEtapa:
    valor: str

    def __post_init__(self) -> None:
        v = self.valor.strip()
        if not v:
            raise ValidationError(
                code="NOMBRE_ETAPA_REQUERIDO",
                message="El nombre de la etapa es obligatorio.",
                field="nombre",
            )
        if len(v) < _MIN or len(v) > _MAX:
            raise ValidationError(
                code="NOMBRE_ETAPA_LONGITUD_INVALIDA",
                message=f"El nombre de la etapa debe tener entre {_MIN} y {_MAX} caracteres.",
                field="nombre",
            )
        if not _FORMATO.match(v):
            raise ValidationError(
                code="NOMBRE_ETAPA_FORMATO_INVALIDO",
                message="El nombre de la etapa solo puede contener letras, números, espacios, guiones y paréntesis.",
                field="nombre",
            )
        object.__setattr__(self, "valor", v)

    def normalizado(self) -> str:
        return self.valor.lower()

    def __str__(self) -> str:
        return self.valor

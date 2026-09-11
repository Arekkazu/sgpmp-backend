"""Value object ``NombreMetrica`` — nombre de una métrica de producción."""
from __future__ import annotations

import re
from dataclasses import dataclass

from src.shared.errors import ValidationError

_FORMATO = re.compile(r"^[A-Za-zÁÉÍÓÚáéíóúÑñ][A-Za-zÁÉÍÓÚáéíóúÑñ0-9 \-()/]*$")

_MIN = 3
_MAX = 60


@dataclass(frozen=True)
class NombreMetrica:
    valor: str

    def __post_init__(self) -> None:
        v = self.valor.strip()
        if not v:
            raise ValidationError(
                code="NOMBRE_METRICA_REQUERIDO",
                message="El nombre de la métrica es obligatorio.",
                field="nombre",
            )
        if len(v) < _MIN or len(v) > _MAX:
            raise ValidationError(
                code="NOMBRE_METRICA_LONGITUD_INVALIDA",
                message=f"El nombre de la métrica debe tener entre {_MIN} y {_MAX} caracteres.",
                field="nombre",
            )
        if not _FORMATO.match(v):
            raise ValidationError(
                code="NOMBRE_METRICA_FORMATO_INVALIDO",
                message="El nombre de la métrica solo puede contener letras, números, espacios, guiones, paréntesis y barras.",
                field="nombre",
            )
        object.__setattr__(self, "valor", v)

    def normalizado(self) -> str:
        return self.valor.lower()

    def __str__(self) -> str:
        return self.valor

"""Value object ``NombreFinca`` — nombre de una finca productiva (RF-19)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from src.shared.errors import ValidationError

_FORMATO = re.compile(r"^[A-Za-zÁÉÍÓÚáéíóúÑñ][A-Za-zÁÉÍÓÚáéíóúÑñ ]*$")
_MIN, _MAX = 1, 55


@dataclass(frozen=True)
class NombreFinca:
    valor: str

    def __post_init__(self) -> None:
        v = self.valor.strip()
        if not v:
            raise ValidationError(
                code="NOMBRE_FINCA_REQUERIDO",
                message="El nombre de la finca es obligatorio.",
                field="nombre",
            )
        if len(v) < _MIN or len(v) > _MAX:
            raise ValidationError(
                code="NOMBRE_FINCA_LONGITUD_INVALIDA",
                message=f"El nombre de la finca debe tener entre {_MIN} y {_MAX} caracteres.",
                field="nombre",
            )
        if not _FORMATO.match(v):
            raise ValidationError(
                code="NOMBRE_FINCA_FORMATO_INVALIDO",
                message=(
                    "El nombre de la finca solo puede contener letras y espacios "
                    "(incluye tildes y ñ). No se permiten números ni caracteres especiales."
                ),
                field="nombre",
            )
        object.__setattr__(self, "valor", v)

    def normalizado(self) -> str:
        return self.valor.lower()

    def __str__(self) -> str:
        return self.valor

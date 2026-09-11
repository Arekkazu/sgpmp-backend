"""Value object ``NombreInfraestructura`` — nombre de un área productiva (RF-20)."""
from __future__ import annotations

from dataclasses import dataclass

from src.shared.errors import ValidationError

_MIN, _MAX = 1, 50


@dataclass(frozen=True)
class NombreInfraestructura:
    valor: str

    def __post_init__(self) -> None:
        v = self.valor.strip()
        if not v:
            raise ValidationError(
                code="NOMBRE_INFRA_REQUERIDO",
                message="El nombre del área productiva es obligatorio.",
                field="nombre_infraestructura",
            )
        if len(v) < _MIN or len(v) > _MAX:
            raise ValidationError(
                code="NOMBRE_INFRA_LONGITUD_INVALIDA",
                message=f"El nombre del área debe tener entre {_MIN} y {_MAX} caracteres.",
                field="nombre_infraestructura",
            )
        object.__setattr__(self, "valor", v)

    def normalizado(self) -> str:
        return self.valor.lower()

    def __str__(self) -> str:
        return self.valor

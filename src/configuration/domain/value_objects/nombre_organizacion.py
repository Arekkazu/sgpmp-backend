"""Value object ``NombreOrganizacion`` — nombre visible de la organización en la plataforma."""
from __future__ import annotations

from dataclasses import dataclass

from src.shared.errors import ValidationError

_MAX = 50
_MIN = 1


@dataclass(frozen=True)
class NombreOrganizacion:
    valor: str

    def __post_init__(self) -> None:
        if not isinstance(self.valor, str):
            raise ValidationError(
                code="NOMBRE_ORGANIZACION_INVALIDO",
                message="El nombre de la organización debe ser texto.",
                field="org_display_name",
            )
        stripped = self.valor.strip()
        if len(stripped) < _MIN or len(stripped) > _MAX:
            raise ValidationError(
                code="NOMBRE_ORGANIZACION_LONGITUD",
                message=(
                    f"El nombre de la organización debe tener entre {_MIN} y {_MAX} caracteres. "
                    f"Longitud recibida: {len(stripped)}."
                ),
                field="org_display_name",
            )

    def __str__(self) -> str:
        return self.valor.strip()

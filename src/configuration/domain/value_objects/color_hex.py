"""Value object ``ColorHex`` — color en formato hexadecimal de 6 dígitos (#RRGGBB)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from src.shared.errors import ValidationError

_HEX_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')


@dataclass(frozen=True)
class ColorHex:
    valor: str

    def __post_init__(self) -> None:
        if not isinstance(self.valor, str) or not _HEX_RE.match(self.valor):
            raise ValidationError(
                code="COLOR_HEX_INVALIDO",
                message=(
                    f"El color debe estar en formato hexadecimal de 6 dígitos (ej. #3A7BD5). "
                    f"Valor recibido: '{self.valor}'."
                ),
                field="color",
            )

    def __str__(self) -> str:
        return self.valor

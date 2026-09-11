"""Value object ``Superficie`` — área física en metros cuadrados (RF-20)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from src.shared.errors import ValidationError


@dataclass(frozen=True)
class Superficie:
    valor: Decimal

    def __post_init__(self) -> None:
        try:
            v = Decimal(str(self.valor))
        except InvalidOperation:
            raise ValidationError(
                code="SUPERFICIE_INVALIDA",
                message="La superficie debe ser un valor numérico.",
                field="superficie",
            )
        if v <= Decimal("0"):
            raise ValidationError(
                code="SUPERFICIE_NO_POSITIVA",
                message=f"La superficie del área productiva debe ser un valor positivo. Valor recibido: {v}.",
                field="superficie",
            )
        object.__setattr__(self, "valor", v)

    def __str__(self) -> str:
        return str(self.valor)

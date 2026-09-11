"""Value object ``TamanoH`` — tamaño de la finca en hectáreas (RF-19)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from src.shared.errors import ValidationError


@dataclass(frozen=True)
class TamanoH:
    valor: Decimal

    def __post_init__(self) -> None:
        try:
            v = Decimal(str(self.valor))
        except InvalidOperation:
            raise ValidationError(
                code="TAMANO_H_INVALIDO",
                message="El tamaño de la finca debe ser un valor numérico.",
                field="tamano_h",
            )
        if v <= Decimal("0"):
            raise ValidationError(
                code="TAMANO_H_NO_POSITIVO",
                message=f"El tamaño de la finca debe ser mayor a cero. Valor recibido: {v}.",
                field="tamano_h",
            )
        object.__setattr__(self, "valor", v)

    def __str__(self) -> str:
        return str(self.valor)

"""Value object ``Heartbeat`` — tiempo máximo sin datos IoT en minutos."""
from __future__ import annotations

from dataclasses import dataclass

from src.shared.errors import ValidationError


@dataclass(frozen=True)
class Heartbeat:
    valor: int

    def __post_init__(self) -> None:
        if not isinstance(self.valor, int) or self.valor <= 0:
            raise ValidationError(
                code="HEARTBEAT_INVALIDO",
                message=f"El heartbeat debe ser un entero positivo mayor a 0. Valor recibido: {self.valor}.",
                field="heartbeat",
            )

    def __str__(self) -> str:
        return str(self.valor)

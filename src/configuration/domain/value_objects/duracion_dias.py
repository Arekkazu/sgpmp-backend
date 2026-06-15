"""Value object ``DuracionDias`` — duración estimada de una etapa en días."""
from __future__ import annotations

from dataclasses import dataclass

from src.shared.errors import ValidationError


@dataclass(frozen=True)
class DuracionDias:
    valor: int

    def __post_init__(self) -> None:
        if not isinstance(self.valor, int) or self.valor <= 0:
            raise ValidationError(
                code="DURACION_DIAS_INVALIDA",
                message=f"La duración estimada debe ser un número entero positivo mayor a 0. Valor recibido: {self.valor}.",
                field="duracion_dias",
            )

    def __str__(self) -> str:
        return str(self.valor)

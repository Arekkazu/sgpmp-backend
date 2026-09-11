"""Value object ``FrecuenciaMuestreo`` — intervalo esperado de datos IoT en minutos."""
from __future__ import annotations

from dataclasses import dataclass

from src.shared.errors import ValidationError


@dataclass(frozen=True)
class FrecuenciaMuestreo:
    valor: int

    def __post_init__(self) -> None:
        if not isinstance(self.valor, int) or self.valor <= 0:
            raise ValidationError(
                code="FRECUENCIA_INVALIDA",
                message=f"La frecuencia de muestreo debe ser un entero positivo mayor a 0. Valor recibido: {self.valor}.",
                field="frecuencia_muestreo",
            )

    def __str__(self) -> str:
        return str(self.valor)

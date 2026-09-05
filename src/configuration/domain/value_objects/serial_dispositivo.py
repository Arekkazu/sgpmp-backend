"""Value object ``SerialDispositivo`` — número de serie físico de un dispositivo IoT (RF-21)."""
from __future__ import annotations

from dataclasses import dataclass

from src.shared.errors import ValidationError

_MIN, _MAX = 1, 50


@dataclass(frozen=True)
class SerialDispositivo:
    valor: str

    def __post_init__(self) -> None:
        v = self.valor.strip()
        if not v:
            raise ValidationError(
                code="SERIAL_REQUERIDO",
                message="El número de serie del dispositivo es obligatorio.",
                field="serial",
            )
        if len(v) > _MAX:
            raise ValidationError(
                code="SERIAL_LONGITUD_INVALIDA",
                message=f"El serial no puede superar los {_MAX} caracteres.",
                field="serial",
            )
        object.__setattr__(self, "valor", v)

    def __str__(self) -> str:
        return self.valor

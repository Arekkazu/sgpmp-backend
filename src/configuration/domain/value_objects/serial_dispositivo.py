"""Value object ``SerialDispositivo`` — número de serie físico de un dispositivo IoT (RF-21)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from src.shared.errors import ValidationError

_MIN, _MAX = 1, 50

# INC-M09-21-G125-01: solo alfanuméricos, guion y guion bajo. Un serial legítimo
# nunca lleva espacios, comillas ni comentarios SQL (`' OR '1'='1' -- `); un
# allow-list explícito los rechaza en el borde de la API en vez de confiar en
# que la parametrización de SQLAlchemy sea la única barrera.
_FORMATO = re.compile(r"^[A-Za-z0-9_-]+$")


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
        if not _FORMATO.match(v):
            raise ValidationError(
                code="SERIAL_FORMATO_INVALIDO",
                message="El serial solo puede contener letras, números, guiones y guiones bajos.",
                field="serial",
            )
        object.__setattr__(self, "valor", v)

    def __str__(self) -> str:
        return self.valor

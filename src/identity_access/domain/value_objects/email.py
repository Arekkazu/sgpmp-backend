"""Value object ``Email`` del dominio de identidad.

Un *value object* es inmutable y se compara por valor: dos ``Email`` con el
mismo texto normalizado son iguales. Valida su formato en el momento de
construirse, de modo que en el resto del dominio es imposible tener en las
manos un correo inválido.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from src.shared.errors import ValidationError

# Formato pragmático: parte local, arroba y dominio con TLD de 2+ letras.
_FORMATO_CORREO = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


@dataclass(frozen=True)
class Email:
    """Dirección de correo electrónico válida y normalizada.

    Attributes:
        valor: Texto del correo, normalizado a minúsculas y sin espacios.

    Raises:
        ValidationError: Si el texto no cumple el formato de correo. HTTP 400.
    """

    valor: str

    def __post_init__(self) -> None:
        normalizado = self.valor.strip().lower()
        if not _FORMATO_CORREO.match(normalizado):
            raise ValidationError(
                code="CORREO_INVALIDO",
                message="El correo electrónico no tiene un formato válido.",
                field="correo_electronico",
            )
        # ``frozen=True`` impide la asignación directa; object.__setattr__ guarda
        # la versión normalizada una sola vez, durante la construcción.
        object.__setattr__(self, "valor", normalizado)

    def __str__(self) -> str:
        return self.valor

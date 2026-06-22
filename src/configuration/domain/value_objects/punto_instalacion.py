"""Value object ``PuntoInstalacion`` — descripción del punto físico de instalación de un sensor (RF-22)."""
from __future__ import annotations

from dataclasses import dataclass

from src.shared.errors import ValidationError

_MIN, _MAX = 1, 100


@dataclass(frozen=True)
class PuntoInstalacion:
    valor: str

    def __post_init__(self) -> None:
        v = self.valor.strip()
        if not v:
            raise ValidationError(
                code="PUNTO_INSTALACION_REQUERIDO",
                message="El punto de instalación del sensor es obligatorio.",
                field="punto_instalacion",
            )
        if len(v) > _MAX:
            raise ValidationError(
                code="PUNTO_INSTALACION_LONGITUD_INVALIDA",
                message=f"El punto de instalación no puede superar los {_MAX} caracteres.",
                field="punto_instalacion",
            )
        object.__setattr__(self, "valor", v)

    def __str__(self) -> str:
        return self.valor

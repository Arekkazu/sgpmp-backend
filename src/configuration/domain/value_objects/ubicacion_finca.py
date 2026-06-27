"""Value object ``UbicacionFinca`` — datos geográficos de una finca (RF-19).

Encapsula el JSONB: departamento, municipio, vereda (solo letras/espacios/tildes/ñ)
y coordenadas latitud (-90 a 90) y longitud (-180 a 180).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from src.shared.errors import ValidationError

_TEXTO = re.compile(r"^[A-Za-zÁÉÍÓÚáéíóúÑñ][A-Za-zÁÉÍÓÚáéíóúÑñ ]*$")


def _validar_texto(valor: str, campo: str) -> str:
    v = valor.strip() if valor else ""
    if not v:
        raise ValidationError(
            code=f"{campo.upper()}_REQUERIDO",
            message=f"El campo '{campo}' es obligatorio.",
            field=campo,
        )
    if not _TEXTO.match(v):
        raise ValidationError(
            code=f"{campo.upper()}_FORMATO_INVALIDO",
            message=(
                f"El campo '{campo}' solo permite letras y espacios "
                "(incluye tildes y ñ). No se permiten números ni caracteres especiales."
            ),
            field=campo,
        )
    return v


@dataclass(frozen=True)
class UbicacionFinca:
    departamento: str
    municipio: str
    vereda: str
    latitud: Decimal
    longitud: Decimal

    def __post_init__(self) -> None:
        dep = _validar_texto(self.departamento, "departamento")
        mun = _validar_texto(self.municipio, "municipio")
        ver = _validar_texto(self.vereda, "vereda")

        lat = Decimal(str(self.latitud))
        lon = Decimal(str(self.longitud))

        if lat < Decimal("-90") or lat > Decimal("90"):
            raise ValidationError(
                code="LATITUD_FUERA_RANGO",
                message="La latitud debe estar entre -90 y 90.",
                field="latitud",
            )
        if lon < Decimal("-180") or lon > Decimal("180"):
            raise ValidationError(
                code="LONGITUD_FUERA_RANGO",
                message="La longitud debe estar entre -180 y 180.",
                field="longitud",
            )

        object.__setattr__(self, "departamento", dep)
        object.__setattr__(self, "municipio", mun)
        object.__setattr__(self, "vereda", ver)
        object.__setattr__(self, "latitud", lat)
        object.__setattr__(self, "longitud", lon)

    def to_dict(self) -> dict:
        return {
            "departamento": self.departamento,
            "municipio": self.municipio,
            "vereda": self.vereda,
            "latitud": str(self.latitud),
            "longitud": str(self.longitud),
        }

    @classmethod
    def from_dict(cls, data: dict) -> UbicacionFinca:
        try:
            return cls(
                departamento=data.get("departamento", ""),
                municipio=data.get("municipio", ""),
                vereda=data.get("vereda", ""),
                latitud=Decimal(str(data.get("latitud", 0))),
                longitud=Decimal(str(data.get("longitud", 0))),
            )
        except (KeyError, TypeError, ValueError):
            raise ValidationError(
                code="UBICACION_FORMATO_INVALIDO",
                message=(
                    "La información de ubicación no cumple con el formato requerido. "
                    "Asegúrese de incluir departamento, municipio, vereda y coordenadas."
                ),
                field="ubicacion",
            )

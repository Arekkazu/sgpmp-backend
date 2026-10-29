"""Schemas de accesibilidad de la identidad visual (RF-26 + RF-27).

Compartidos por la respuesta de identidad visual (RF-26, que el administrador ve al
guardar) y por el contexto de interfaz (RF-25, que todos los roles leen al arrancar la
sesión). Es la misma información y debe tener la misma forma en los dos sitios.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from src.configuration.domain.entities import accesibilidad_visual as dominio


class ContrasteTemaResponse(BaseModel):
    """Contraste del color contra el fondo de un tema; ``color_ajustado`` es la variante
    que cumple AA.
    """
    fondo: str
    ratio: float
    cumple_aa: bool
    color_ajustado: str
    aviso: Optional[str]


class ContrasteColorResponse(BaseModel):
    """Contraste del color en el tema claro y en el oscuro."""
    claro: ContrasteTemaResponse
    oscuro: ContrasteTemaResponse


class AccesibilidadResponse(BaseModel):
    """Evaluación WCAG 2.1 AA (4.5:1) de los colores de la identidad visual."""
    minimo_aa: float
    primary_color: Optional[ContrasteColorResponse]
    secondary_color: Optional[ContrasteColorResponse]

    @classmethod
    def from_entity(
        cls, entity: Optional[dominio.AccesibilidadVisual]
    ) -> Optional[AccesibilidadResponse]:
        if entity is None:
            return None
        return cls(
            minimo_aa=entity.minimo_aa,
            primary_color=_color(entity.primary_color),
            secondary_color=_color(entity.secondary_color),
        )


def _color(valor: Optional[dominio.ContrasteColor]) -> Optional[ContrasteColorResponse]:
    if valor is None:
        return None
    return ContrasteColorResponse(
        claro=ContrasteTemaResponse(**vars(valor.claro)),
        oscuro=ContrasteTemaResponse(**vars(valor.oscuro)),
    )

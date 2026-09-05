"""Schema de respuesta para identidad visual institucional (RF-26)."""
from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel

from src.configuration.domain.entities import accesibilidad_visual
from src.configuration.infrastructure.schema.accesibilidad_schema import AccesibilidadResponse


class IdentidadVisualResponse(BaseModel):
    id_identidad_visual: int
    id_finca: int
    id_usuario: int
    logo_path: Optional[str]
    primary_color: Optional[str]
    secondary_color: Optional[str]
    org_display_name: Optional[str]
    version: Optional[int]
    fecha_creacion: Optional[datetime.datetime]
    # Contraste WCAG 2.1 AA de los colores contra los dos temas (RF-27). Es informativo:
    # un color que no cumple se guarda igual, porque el RF pide advertir y ajustar, no
    # rechazar. `accesibilidad.avisos` trae el texto que el administrador debe ver.
    accesibilidad: Optional[AccesibilidadResponse]

    model_config = {"from_attributes": True}

    @classmethod
    def from_entity(cls, entity) -> IdentidadVisualResponse:
        # Las tres columnas son nullable en `modulo9.identidad_visuales`: una fila escrita
        # fuera de la API puede traerlas vacías y leer `.valor` sobre `None` reventaba con
        # AttributeError en vez de devolver el registro.
        return cls(
            id_identidad_visual=entity.id_identidad_visual,
            id_finca=entity.id_finca,
            id_usuario=entity.id_usuario,
            logo_path=entity.logo_path,
            primary_color=entity.primary_color.valor if entity.primary_color else None,
            secondary_color=entity.secondary_color.valor if entity.secondary_color else None,
            org_display_name=entity.org_display_name.valor if entity.org_display_name else None,
            version=entity.version,
            fecha_creacion=entity.fecha_creacion,
            accesibilidad=AccesibilidadResponse.from_entity(
                accesibilidad_visual.evaluar(entity.primary_color, entity.secondary_color)
            ),
        )

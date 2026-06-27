"""Schema de respuesta para identidad visual institucional (RF-26)."""
from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel


class IdentidadVisualResponse(BaseModel):
    id_identidad_visual: int
    id_finca: int
    id_usuario: int
    logo_path: Optional[str]
    primary_color: str
    secondary_color: str
    org_display_name: str
    version: Optional[int]
    fecha_creacion: Optional[datetime.datetime]

    model_config = {"from_attributes": True}

    @classmethod
    def from_entity(cls, entity) -> IdentidadVisualResponse:
        return cls(
            id_identidad_visual=entity.id_identidad_visual,
            id_finca=entity.id_finca,
            id_usuario=entity.id_usuario,
            logo_path=entity.logo_path,
            primary_color=entity.primary_color.valor,
            secondary_color=entity.secondary_color.valor,
            org_display_name=entity.org_display_name.valor,
            version=entity.version,
            fecha_creacion=entity.fecha_creacion,
        )

"""Schema de respuesta para preferencia de tema visual (RF-27)."""
from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel


class TemaVisualResponse(BaseModel):
    id_tema_visual: int
    id_usuario: int
    theme_mode: int
    es_global: bool
    fecha_actualizacion: Optional[datetime.datetime]

    model_config = {"from_attributes": True}

    @classmethod
    def from_entity(cls, entity) -> TemaVisualResponse:
        return cls(
            id_tema_visual=entity.id_tema_visual,
            id_usuario=entity.id_usuario,
            theme_mode=int(entity.theme_mode),
            es_global=entity.es_global,
            fecha_actualizacion=entity.fecha_actualizacion,
        )


class TemaResueltoResponse(BaseModel):
    theme_mode: int
    fuente: str
    id_tema_visual: Optional[int]

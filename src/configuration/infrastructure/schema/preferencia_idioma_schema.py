"""Schema de respuesta para preferencia de idioma (RF-29)."""
from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel


class PreferenciaIdiomaResponse(BaseModel):
    id_preferencia_idioma: int
    id_usuario: int
    locale_code: str
    es_por_defecto: bool
    fecha_actualizacion: Optional[datetime.datetime]

    model_config = {"from_attributes": True}

    @classmethod
    def from_entity(cls, entity) -> PreferenciaIdiomaResponse:
        return cls(
            id_preferencia_idioma=entity.id_preferencia_idioma,
            id_usuario=entity.id_usuario,
            locale_code=entity.locale_code,
            es_por_defecto=entity.es_por_defecto,
            fecha_actualizacion=entity.fecha_actualizacion,
        )


class IdiomaResueltoResponse(BaseModel):
    locale_code: str
    fuente: str
    id_preferencia_idioma: Optional[int]

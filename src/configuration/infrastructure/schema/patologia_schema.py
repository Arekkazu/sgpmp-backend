"""Schemas de respuesta para los endpoints de patologías por especie (RF-16)."""
from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class PatologiaEspecieItemResponse(BaseModel):
    """Patología configurada para una especie (entidad M09 `especies_patologias`)."""

    id_especies_patologias: int
    id_patologia: Optional[int]
    id_especie: int
    nombre: str
    descripcion: Optional[str]
    es_activo: bool
    fecha_actualizacion: Optional[datetime.datetime]

    model_config = {"from_attributes": True}

    @field_validator("nombre", mode="before")
    @classmethod
    def extraer_nombre(cls, v: object) -> str:
        if hasattr(v, "valor"):
            return v.valor  # type: ignore[attr-defined]
        return str(v)


class PatologiasPorEspecieResponse(BaseModel):
    total: int
    items: list[PatologiaEspecieItemResponse]

"""Schemas de respuesta para los endpoints de etapas del ciclo productivo (RF-16)."""
from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class CicloBiologicoResponse(BaseModel):
    id_ciclo_biologico: int
    nombre: str
    descripcion: Optional[str]
    duracion_dias: int
    id_especie: int
    es_activo: bool
    fecha_actualizacion: Optional[datetime.datetime]

    model_config = {"from_attributes": True}

    @field_validator("nombre", mode="before")
    @classmethod
    def extraer_nombre(cls, v: object) -> str:
        if hasattr(v, "valor"):
            return v.valor  # type: ignore[attr-defined]
        return str(v)

    @field_validator("duracion_dias", mode="before")
    @classmethod
    def extraer_duracion(cls, v: object) -> int:
        if hasattr(v, "valor"):
            return v.valor  # type: ignore[attr-defined]
        return int(v)  # type: ignore[arg-type]


class EtapasPorEspecieResponse(BaseModel):
    total: int
    items: list[CicloBiologicoResponse]

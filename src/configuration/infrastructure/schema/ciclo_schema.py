# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | #391 RF-16: densidad y biomasa máximas de la etapa con aviso preventivo |
"""Schemas de respuesta para los endpoints de etapas del ciclo productivo (RF-16)."""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, field_validator


class CicloBiologicoResponse(BaseModel):
    """Etapa del ciclo productivo de una especie."""
    id_ciclo_biologico: int
    nombre: str
    descripcion: Optional[str]
    duracion_dias: int
    id_especie: int
    es_activo: bool
    fecha_actualizacion: Optional[datetime.datetime]
    densidad_maxima: Optional[Decimal] = None
    biomasa_maxima: Optional[Decimal] = None
    aviso_preventivo_pct: int = 90

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
    """Etapas del ciclo de una especie."""
    total: int
    items: list[CicloBiologicoResponse]

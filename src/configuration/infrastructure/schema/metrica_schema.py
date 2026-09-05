"""Schemas de respuesta para los endpoints de métricas de producción (RF-16)."""
from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class MetricaProduccionResponse(BaseModel):
    """Respuesta de operaciones sobre una métrica (registrar, editar, desactivar)."""

    id_metrica_produccion: int
    nombre: str
    unidad_medida: str
    tipo_medicion: str
    aplica_a_tipo_activo: str
    id_especie: Optional[int]
    es_activo: bool
    fecha_actualizacion: Optional[datetime.datetime]

    model_config = {"from_attributes": True}

    @field_validator("nombre", mode="before")
    @classmethod
    def extraer_nombre(cls, v: object) -> str:
        if hasattr(v, "valor"):
            return v.valor  # type: ignore[attr-defined]
        return str(v)

    @field_validator("tipo_medicion", mode="before")
    @classmethod
    def extraer_tipo_medicion(cls, v: object) -> str:
        if hasattr(v, "value"):
            return v.value  # type: ignore[attr-defined]
        return str(v)

    @field_validator("aplica_a_tipo_activo", mode="before")
    @classmethod
    def extraer_aplica(cls, v: object) -> str:
        if hasattr(v, "value"):
            return v.value  # type: ignore[attr-defined]
        return str(v)


class MetricasPorEspecieResponse(BaseModel):
    total: int
    items: list[MetricaProduccionResponse]

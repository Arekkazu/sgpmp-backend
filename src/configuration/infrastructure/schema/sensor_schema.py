"""Schemas de respuesta para endpoints de sensores (RF-22)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SensorResponse(BaseModel):
    id_sensores: int
    nombre: str
    id_dispositivo_iot: int
    es_activo: bool
    categoria: Optional[str]

    model_config = {"from_attributes": True}

    @classmethod
    def from_entity(cls, sensor) -> SensorResponse:
        return cls(
            id_sensores=sensor.id_sensores,
            nombre=sensor.nombre,
            id_dispositivo_iot=sensor.id_dispositivo_iot,
            es_activo=sensor.es_activo,
            categoria=sensor.categoria,
        )


class ListaSensoresResponse(BaseModel):
    total: int
    items: list[SensorResponse]

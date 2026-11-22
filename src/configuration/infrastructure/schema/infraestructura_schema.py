# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-22 RF-20: la salida trae especies, nivel_criticidad y capacidad_maxima derivada |
"""Schemas de respuesta para los endpoints de infraestructura productiva (RF-20)."""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class InfraestructuraResponse(BaseModel):
    """Área productiva registrada."""
    id_infraestructura: int
    nombre_infraestructura: str
    tipo_area: str
    superficie: Decimal
    id_finca: int
    descripcion_infraestructura: Optional[str]
    es_activo: bool
    fecha_actualizacion: Optional[datetime.datetime]
    especies: list[int] = []
    especie_id: Optional[int] = Field(
        default=None, json_schema_extra={"deprecated": True},
        description="Deprecado (RFC-012): la especie si el área tiene una sola; usar especies.",
    )
    tipo_modelo_asignado: Optional[str] = None
    nivel_criticidad: str = "MEDIA"
    # RFC-012: derivada, floor(MIN densidad ind/m² × superficie); None si alguna especie no tiene densidad.
    capacidad_maxima: Optional[int] = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_entity(cls, infra) -> InfraestructuraResponse:
        return cls(
            id_infraestructura=infra.id_infraestructura,
            nombre_infraestructura=infra.nombre.valor,
            tipo_area=infra.tipo,
            superficie=infra.superficie.valor,
            id_finca=infra.id_finca,
            descripcion_infraestructura=infra.descripcion,
            es_activo=infra.es_activo,
            fecha_actualizacion=infra.fecha_actualizacion,
            especies=list(infra.id_especies),
            especie_id=infra.id_especie,
            tipo_modelo_asignado=infra.tipo_modelo_asignado,
            nivel_criticidad=infra.nivel_criticidad,
            capacidad_maxima=infra.capacidad_maxima,
        )


class ListaInfraestructurasResponse(BaseModel):
    """Áreas productivas de una finca."""
    total: int
    items: list[InfraestructuraResponse]

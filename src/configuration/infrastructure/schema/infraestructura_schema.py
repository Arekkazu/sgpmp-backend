"""Schemas de respuesta para los endpoints de infraestructura productiva (RF-20)."""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


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
    especie_id: Optional[int] = None
    tipo_modelo_asignado: Optional[str] = None

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
            especie_id=infra.id_especie,
            tipo_modelo_asignado=infra.tipo_modelo_asignado,
        )


class ListaInfraestructurasResponse(BaseModel):
    """Áreas productivas de una finca."""
    total: int
    items: list[InfraestructuraResponse]

"""Schemas de respuesta para el catálogo de tipos de área (RF-20)."""
from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel


class TipoAreaResponse(BaseModel):
    """Datos de un tipo de área del catálogo."""

    id_tipo_area: int
    nombre: str
    es_activo: bool
    fecha_creacion: datetime.datetime
    fecha_actualizacion: Optional[datetime.datetime]

    model_config = {"from_attributes": True}


class ListaTiposAreaResponse(BaseModel):
    """Resultado de la consulta del catálogo de tipos de área."""

    total: int
    items: list[TipoAreaResponse]

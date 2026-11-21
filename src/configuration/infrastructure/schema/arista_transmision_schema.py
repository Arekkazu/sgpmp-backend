# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RFC-021 RF-110 C21.1: respuesta de una arista de transmisión     |
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AristaTransmisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_arista_transmision: int
    id_infraestructura_origen: int
    id_infraestructura_destino: int
    via: str
    direccion: str
    intensidad: Decimal
    factor_barrera: Decimal
    peso: Decimal
    origen_dato: str
    descripcion: Optional[str] = None
    es_activo: bool
    fecha_creacion: Optional[datetime] = None
    fecha_actualizacion: Optional[datetime] = None

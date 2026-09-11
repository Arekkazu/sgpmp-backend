from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TelemetriaResponse(BaseModel):
    id_telemetria: int
    estado_calidad: str
    timestamp_procesamiento: datetime
    latencia_procesamiento_ms: Optional[int] = None


class ItemBatchResponse(BaseModel):
    sensor_id: int
    timestamp_captura: datetime
    estado: str
    id_telemetria: Optional[int] = None
    error: Optional[str] = None


class IngestaBatchResponse(BaseModel):
    total: int
    aceptados: int
    rechazados: int
    duplicados: int
    detalle: list[ItemBatchResponse]

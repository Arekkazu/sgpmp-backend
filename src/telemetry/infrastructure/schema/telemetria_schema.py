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


class ObservacionVisionResponse(BaseModel):
    id_observacion_vision: int
    timestamp_captura: datetime
    indice_calidad: int
    clasificacion_calidad: str
    apto_para_ia: bool
    # RF-62 v2.0: siempre false para visión.
    apto_para_nic41: bool = False


class IngestaVisionResponse(BaseModel):
    total: int
    aceptadas: int
    duplicadas: int
    observaciones: list[ObservacionVisionResponse]

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TelemetriaCalidadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_evaluacion: UUID
    id_telemetria: int
    id_sensor: int
    timestamp_evaluacion: datetime
    indice_calidad: Optional[int]
    clasificacion_calidad: str
    apto_para_ia: bool
    apto_para_nic41: bool
    flags_detectados: dict
    version_limites_fisicos_aplicada: Optional[str]
    parametros_aplicados: dict
    parametros_calibracion_aplicados: Optional[dict]
    estado_evaluacion: str
    motivo_reevaluacion: Optional[str]
    id_evaluacion_superada: Optional[UUID]
    version_evaluacion: Optional[str]
    fecha_creacion: Optional[datetime]


class ListaCalidadSchema(BaseModel):
    total: int
    pagina: int
    por_pagina: int
    items: list[TelemetriaCalidadSchema]


class ReevaluacionResponseSchema(BaseModel):
    evaluaciones_superadas: int
    evaluaciones_creadas: int

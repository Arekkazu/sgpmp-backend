# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-02 | Arekkazu | AJF-07 RF-53: respuesta del monitor de ingesta |
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class LecturaIngestaSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_bitacora_ingest: int
    fecha_evento: datetime
    fecha_captura_dato: Optional[datetime]
    tipo_evento: Optional[str]
    estado_calidad: Optional[str]
    severidad: Optional[str]
    descripcion: Optional[str]
    id_sensor: Optional[int]
    nombre_sensor: Optional[str]
    id_dispositivo_iot: Optional[int]
    serial_dispositivo: Optional[str]
    nombre_area: Optional[str]
    gateway_id: Optional[str]
    id_telemetria: Optional[int]
    nombre_variable: Optional[str] = None
    categoria_variable: Optional[str] = None
    valor_crudo: Optional[Decimal] = None
    valor_ajustado: Optional[Decimal] = None
    unidad_medida: Optional[str] = None
    origen: Optional[str] = None
    tipo_dato: Optional[str] = None
    latencia_ms: Optional[int] = None
    calibrado: Optional[bool] = None
    valor_agregado: Optional[bool] = None
    latencia_alta: Optional[bool] = None
    frecuencia_anomala: Optional[bool] = None
    posible_drift: Optional[bool] = None
    payload_recibido: Optional[dict] = None


class ListaIngestaSchema(BaseModel):
    items: list[LecturaIngestaSchema]
    total: int
    pagina: int
    por_pagina: int
    desde: datetime
    hasta: datetime


class IndicadoresIngestaSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total: int
    validas: int
    fuera_de_rango: int
    errores: int

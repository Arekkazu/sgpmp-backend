# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-02 | Arekkazu | AJF-07 RF-53: read-model del monitor de ingesta (modulo3.bitacora_ingest) |
"""AJF-07: lo que el monitor de ingesta muestra de cada evento de la bitácora de ingesta.

La fuente es ``modulo3.bitacora_ingest``; los datos de la lectura (valor, origen,
latencia, banderas) vienen de ``modulo3.telemetrias`` solo cuando el evento la
persistió (los rechazos solo quedan en la bitácora).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class LecturaIngesta:
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
    payload_recibido: Optional[dict] = field(default=None)


@dataclass(frozen=True)
class FiltrosIngesta:
    desde: datetime
    hasta: datetime
    ids_fincas: Optional[list[int]]
    estado_calidad: Optional[str] = None
    origen: Optional[str] = None
    id_dispositivo_iot: Optional[int] = None
    id_sensor: Optional[int] = None
    pagina: int = 1
    por_pagina: int = 50


@dataclass(frozen=True)
class IndicadoresIngesta:
    """Eventos del periodo: total, válidas, fuera de rango y errores (rechazos y fallos)."""
    total: int
    validas: int
    fuera_de_rango: int
    errores: int

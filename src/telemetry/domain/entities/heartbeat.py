# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-126-G27 RF-54: transportar el snapshot opcional de métricas del buffer sin ORM. |
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional


@dataclass
class Heartbeat:
    id_heartbeat: Optional[int]
    id_dispositivo_iot: int
    tipo_mensaje: str
    nivel_bateria_pct: Optional[Decimal]
    calidad_senal_rssi: Optional[Decimal]
    calidad_senal_snr: Optional[Decimal]
    estado_local_buffer: Optional[str]
    datos_pendientes_buffer: int
    version_firmware: Optional[str]
    coordenadas: Optional[Any]
    fecha_registro: datetime
    fecha_recepcion: datetime
    reloj_sincronizado: bool
    sensores_operativos: Optional[list[dict[str, Any]]] = None
    temperatura_dispositivo: Optional[Decimal] = None
    metricas_buffer: Optional[dict[str, Any]] = None

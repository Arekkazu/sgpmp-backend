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

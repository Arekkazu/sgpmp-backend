from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel


class HeartbeatReciboSchema(BaseModel):
    id_heartbeat: int
    id_dispositivo_iot: int
    tipo_mensaje: str
    nivel_bateria_pct: Optional[Decimal] = None
    calidad_senal_rssi: Optional[Decimal] = None
    calidad_senal_snr: Optional[Decimal] = None
    estado_local_buffer: Optional[str] = None
    datos_pendientes_buffer: int
    version_firmware: Optional[str] = None
    coordenadas: Optional[Any] = None
    fecha_registro: datetime
    fecha_recepcion: datetime
    reloj_sincronizado: bool

    model_config = {'from_attributes': True}


class EventoBufferReciboSchema(BaseModel):
    """Respuesta de POST /iot/eventos-buffer (RF-54 → RF-60, D10)."""

    id_alerta: int
    es_duplicado: bool  # True: se contó en la alerta técnica abierta del mismo tipo
    tipo_alerta_tecnica: str
    severidad: str

    model_config = {'from_attributes': True}

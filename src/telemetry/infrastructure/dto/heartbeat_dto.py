from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import Field, field_validator

from src.shared.base_dto import BaseDTO


class HeartbeatDTO(BaseDTO):
    """Body del POST /iot/heartbeat enviado por el dispositivo AIOT (payload A.7)."""

    tipo_mensaje: str = Field(..., min_length=1, max_length=30)
    nivel_bateria_pct: Optional[Decimal] = Field(None, ge=0, le=100)
    calidad_senal_rssi: Optional[Decimal] = None
    calidad_senal_snr: Optional[Decimal] = None
    # 'I'=INACTIVO, 'A'=ACTIVO, 'L'=LLENO
    estado_local_buffer: Optional[str] = Field(None, max_length=1)
    datos_pendientes_buffer: int = Field(0, ge=0)
    version_firmware: Optional[str] = Field(None, max_length=50)
    coordenadas: Optional[Any] = None
    fecha_registro: datetime
    reloj_sincronizado: bool = False

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import ConfigDict, Field, StrictBool, StrictStr, field_validator

from src.shared.base_dto import BaseDTO


class SensorOperativoDTO(BaseDTO):
    """Identificador del sobre D11; no se inventa una correspondencia con IDs SQL."""
    model_config = ConfigDict(extra='forbid')

    sensor: StrictStr = Field(min_length=1)
    operativo: StrictBool


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
    sensores_operativos: Optional[list[SensorOperativoDTO]] = None
    # Precisión de NUMERIC(5,2) de DB-03, no un rango físico inventado.
    temperatura_dispositivo: Optional[Decimal] = Field(None, allow_inf_nan=False, max_digits=5, decimal_places=2)

    @field_validator('temperatura_dispositivo', mode='before')
    @classmethod
    def validar_temperatura_numerica(cls, valor):
        if valor is not None and (isinstance(valor, bool) or not isinstance(valor, (int, float, Decimal))):
            raise ValueError('La temperatura del dispositivo debe ser un número finito en °C.')
        return valor

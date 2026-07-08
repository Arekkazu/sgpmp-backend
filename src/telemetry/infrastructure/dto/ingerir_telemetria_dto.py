from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import Field, field_validator

from src.shared.base_dto import BaseDTO


class IngerirTelemetriaDTO(BaseDTO):
    device_id: int = Field(..., gt=0)
    sensor_id: int = Field(..., gt=0)
    tipo_variable: str = Field(..., min_length=2, max_length=40)
    valor: Decimal = Field(...)
    unidad: str = Field(..., min_length=1, max_length=20)
    timestamp_captura: datetime
    access_key: str = Field(..., min_length=1, max_length=100)

    # Opcionales
    timestamp_envio: Optional[datetime] = None
    origen: str = Field(default='TIEMPO_REAL', max_length=20)
    frecuencia_muestreo: Optional[int] = Field(default=None, gt=0)
    valor_agregado: bool = False
    ventana_agregacion: Optional[int] = Field(default=None, gt=0)
    latitud: Optional[Decimal] = None
    longitud: Optional[Decimal] = None
    estado_conectividad: Optional[bool] = None
    nivel_bateria: Optional[Decimal] = Field(default=None, ge=0, le=100)
    calidad_senal_rssi: Optional[Decimal] = None
    calidad_senal_snr: Optional[Decimal] = None
    checksum: Optional[str] = None
    categoria_variable: Optional[str] = None

    @field_validator('origen')
    @classmethod
    def validar_origen(cls, v: str) -> str:
        valores_validos = {'TIEMPO_REAL', 'BUFFER_LOCAL', 'EDGE_AGREGADO'}
        if v.upper() not in valores_validos:
            raise ValueError(f"origen debe ser uno de: {', '.join(valores_validos)}")
        return v.upper()

    @field_validator('tipo_variable')
    @classmethod
    def normalizar_tipo_variable(cls, v: str) -> str:
        return v.upper().strip()


class IngerirTelemetriaBatchDTO(BaseDTO):
    registros: list[IngerirTelemetriaDTO] = Field(..., min_length=1, max_length=500)
    idempotency_key: Optional[str] = None

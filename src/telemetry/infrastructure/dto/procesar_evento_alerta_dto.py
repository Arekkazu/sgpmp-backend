from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import Field, field_validator

from src.shared.base_dto import BaseDTO


class ProcesarEventoAlertaDTO(BaseDTO):
    device_id: int = Field(..., gt=0)
    sensor_id: int = Field(..., gt=0)
    access_key: str = Field(..., min_length=1, max_length=100)

    tipo_variable: str = Field(..., min_length=2, max_length=50)
    valor: Decimal = Field(...)
    unidad: str = Field(..., min_length=1, max_length=20)
    timestamp_evento: datetime
    estado_dato: str = Field(..., min_length=2, max_length=30)
    severidad_edge: str = Field(..., min_length=2, max_length=20)
    origen_evento: str = Field(..., min_length=2, max_length=20)

    # Trazabilidad: al menos uno debe estar presente
    id_evento_edge_computing: Optional[int] = None
    id_telemetria: Optional[int] = None
    id_paquete_inferencia: Optional[int] = None

    reglas_activadas: list[str] = Field(default_factory=list)

    # Datos de IA (para PREDICCION_PATOLOGIA o conflictos Edge vs IA)
    tipo_alerta_ia: Optional[str] = None
    severidad_ia: Optional[str] = None
    probabilidad_ia: Optional[Decimal] = Field(default=None, ge=0, le=1)

    correlacion_variables: Optional[dict[str, Any]] = None
    metadata_evento: Optional[dict[str, Any]] = None

    @field_validator('tipo_variable')
    @classmethod
    def normalizar_tipo_variable(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator('estado_dato')
    @classmethod
    def validar_estado_dato(cls, v: str) -> str:
        validos = {'LECTURA_VALIDA', 'FUERA_DE_RANGO', 'ERROR_CALIBRACION'}
        v = v.upper()
        if v not in validos:
            raise ValueError(f"estado_dato debe ser uno de: {', '.join(validos)}")
        return v

    @field_validator('severidad_edge', 'severidad_ia')
    @classmethod
    def validar_severidad(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        validos = {'LEVE', 'MODERADO', 'CRITICO'}
        v = v.upper()
        if v not in validos:
            raise ValueError(f"severidad debe ser uno de: {', '.join(validos)}")
        return v

    @field_validator('origen_evento')
    @classmethod
    def validar_origen(cls, v: str) -> str:
        validos = {'EDGE', 'BACKEND', 'IA'}
        v = v.upper()
        if v not in validos:
            raise ValueError(f"origen_evento debe ser uno de: {', '.join(validos)}")
        return v

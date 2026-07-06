from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import field_validator

from src.shared.base_dto import BaseDTO


class VariableInvolucradaDTO(BaseDTO):
    tipo_variable: str
    valor: Decimal
    unidad: str
    timestamp_captura: Optional[datetime] = None


class RecibirEventoEdgeDTO(BaseDTO):
    device_id: int
    sensor_id: int
    access_key: str
    # Clasificación producida por RF-55 en el dispositivo Edge
    clasificacion_rf55: str       # NORMAL | DESVIACION_SIMPLE | DESVIACION_COMPUESTA | ERROR_CONFIGURACION
    severidad: Optional[str] = None  # LEVE | MODERADO | CRITICO
    variables_involucradas: list[VariableInvolucradaDTO]
    timestamp_captura: datetime
    timestamp_procesamiento_edge: datetime
    origen: str = "TIEMPO_REAL"   # TIEMPO_REAL | BUFFER_LOCAL
    estado_conectividad: bool
    metadata_edge: Optional[dict[str, Any]] = None
    version_modelo_objetivo: Optional[str] = None

    @field_validator('clasificacion_rf55')
    @classmethod
    def validar_clasificacion(cls, v: str) -> str:
        validos = {"NORMAL", "DESVIACION_SIMPLE", "DESVIACION_COMPUESTA", "ERROR_CONFIGURACION"}
        if v not in validos:
            raise ValueError(f"clasificacion_rf55 debe ser uno de: {', '.join(sorted(validos))}")
        return v

    @field_validator('severidad')
    @classmethod
    def validar_severidad(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in {"LEVE", "MODERADO", "CRITICO"}:
            raise ValueError("severidad debe ser LEVE, MODERADO o CRITICO")
        return v

    @field_validator('origen')
    @classmethod
    def validar_origen(cls, v: str) -> str:
        if v not in {"TIEMPO_REAL", "BUFFER_LOCAL"}:
            raise ValueError("origen debe ser TIEMPO_REAL o BUFFER_LOCAL")
        return v

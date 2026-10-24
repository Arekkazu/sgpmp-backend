"""DTO del aviso de buffer del Gateway Edge (POST /iot/eventos-buffer, RF-54 E1/E6).

Sobre de D10 (AIOT-DEV-03): el nodo lo publica en ``sgpmp/<serial>/status`` con
``tipo_mensaje = EVENTO_BUFFER`` y el broker lo reenvía tal cual, más el
``serial`` del tópico.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import Field

from src.shared.base_dto import BaseDTO


class EventoBuffer(str, Enum):
    BUFFER_OVERFLOW = "BUFFER_OVERFLOW"
    BUFFER_DATA_CORRUPTION = "BUFFER_DATA_CORRUPTION"


class RecibirEventoBufferDTO(BaseDTO):
    serial: str = Field(..., min_length=1, max_length=100)
    evento: EventoBuffer
    porcentaje_ocupacion: Decimal = Field(..., ge=0, le=100)
    # POLITICA_RECHAZO / POLITICA_SOBRESCRITURA en un overflow (RF-54 Fase 4); una
    # corrupción no aplica política. Texto libre: lo define el firmware.
    politica_aplicada: Optional[str] = Field(default=None, max_length=50)
    cantidad_datos_afectados: int = Field(..., ge=0)
    timestamp_evento: datetime

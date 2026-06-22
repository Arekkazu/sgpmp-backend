"""Schemas de respuesta para endpoints de calibración de sensores (RF-24)."""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class CalibracionResponse(BaseModel):
    id_calibracion: int
    id_dispositivo_iot: int
    id_sensor: int
    valor_referencia: Decimal
    fecha_calibracion: datetime.datetime
    id_usuario: int
    observaciones: Optional[str]

    model_config = {"from_attributes": True}

    @classmethod
    def from_entity(cls, calibracion) -> CalibracionResponse:
        return cls(
            id_calibracion=calibracion.id_calibracion,
            id_dispositivo_iot=calibracion.id_dispositivo_iot,
            id_sensor=calibracion.id_sensor,
            valor_referencia=calibracion.valor_referencia,
            fecha_calibracion=calibracion.fecha_calibracion,
            id_usuario=calibracion.id_usuario,
            observaciones=calibracion.observaciones,
        )


class ListaCalibracionesResponse(BaseModel):
    total: int
    items: list[CalibracionResponse]

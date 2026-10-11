"""DTO de ingesta de observaciones de visión (POST /iot/telemetria/vision, RF-53/RF-56 v2.0).

Contrato PROVISIONAL hasta ET-01 (INC-M09-77-G137, #513). Los nombres de las
dimensiones de calidad son los de RFC-011 / RF-62 v2.0.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field, FiniteFloat

from src.shared.base_dto import BaseDTO
from src.telemetry.domain.entities.observacion_vision import EstadoCalibracionCamara


class ObservacionVisionDTO(BaseDTO):
    timestamp_captura: datetime
    cobertura_ventana: Decimal = Field(..., ge=0, le=1, decimal_places=4)
    n_tracks: int = Field(..., ge=0)
    n_tracks_perdidos: int = Field(..., ge=0)
    fps_efectivo: Decimal = Field(..., ge=0, max_digits=6, decimal_places=2)
    estado_calibracion: EstadoCalibracionCamara
    # Vector de comportamiento del área: componente → valor (p. ej.
    # densidad_actividad, tasa_movimiento). RF-24 VISION calibra cada uno.
    vector: dict[str, FiniteFloat] = Field(..., min_length=1)


class IngerirObservacionesVisionDTO(BaseDTO):
    device_id: int = Field(..., gt=0)
    access_key: str = Field(..., min_length=1, max_length=100)
    # RF-56 v2.0: el sobre de visión lleva el área observada.
    area_id: int = Field(..., gt=0)
    observaciones: list[ObservacionVisionDTO] = Field(..., min_length=1, max_length=500)

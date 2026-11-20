# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
# | 2026-11-19 | Arekkazu | SEG-M03-03 RF-56: vector acotado en número de componentes y largo del nombre |
"""DTO de ingesta de observaciones de visión (POST /iot/telemetria/vision, RF-53/RF-56 v2.0).

Lote legado INC-M09-77-G137 (#513), conservado por compatibilidad. El sobre
D4 se declara por separado en observacion_vision_d4_dto.py. Las diferencias
con AIOT-SPEC-01 y el catálogo SQL están documentadas en el informe DEV-07.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import ConfigDict, Field, FiniteFloat, StringConstraints

from src.shared.base_dto import BaseDTO
from src.telemetry.domain.entities.observacion_vision import EstadoCalibracionCamara
from src.shared.fechas import FechaHoraUtc


class ObservacionVisionDTO(BaseDTO):
    model_config = ConfigDict(extra='forbid')
    timestamp_captura: FechaHoraUtc
    cobertura_ventana: Decimal = Field(..., ge=0, le=1, decimal_places=4)
    n_tracks: int = Field(..., ge=0)
    n_tracks_perdidos: int = Field(..., ge=0)
    fps_efectivo: Decimal = Field(..., ge=0, max_digits=6, decimal_places=2)
    estado_calibracion: EstadoCalibracionCamara
    # Vector de comportamiento del área: componente → valor (p. ej.
    # densidad_actividad, tasa_movimiento). RF-24 VISION calibra cada uno.
    # SEG-M03-03: acotado para que 500 observaciones no disparen memoria ni CPU antes de validar.
    vector: dict[Annotated[str, StringConstraints(min_length=1, max_length=64)], FiniteFloat] = Field(
        ..., min_length=1, max_length=32)


class IngerirObservacionesVisionDTO(BaseDTO):
    model_config = ConfigDict(extra='forbid')
    device_id: int = Field(..., gt=0)
    serial: str = Field(..., min_length=1, max_length=100)
    # RF-56 v2.0: el sobre de visión lleva el área observada.
    area_id: int = Field(..., gt=0)
    observaciones: list[ObservacionVisionDTO] = Field(..., min_length=1, max_length=500)

"""DTO de entrada para la calibración por visión (POST /configuracion/calibraciones-vision, RF-24 v2.0)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import model_validator

from src.configuration.domain.value_objects.modo_calibracion import ModoCalibracion
from src.shared.base_dto import BaseDTO


class VentanaObservacionDTO(BaseDTO):
    """Rango temporal de las observaciones de visión usadas para el cálculo."""
    inicio: datetime
    fin: datetime

    @model_validator(mode="after")
    def validar_rango(self) -> "VentanaObservacionDTO":
        if self.fin <= self.inicio:
            raise ValueError("La ventana de observación debe terminar después de su inicio.")
        return self


class CalibrarVisionDTO(BaseDTO):
    """Calibración por visión de un área: ventana de observaciones a usar y fecha de la
    calibración.
    """
    # RF-24 v2.0: discriminador obligatorio; este endpoint solo acepta VISION.
    modo_calibracion: Literal[ModoCalibracion.VISION]
    area_id: int
    ventana_observacion: VentanaObservacionDTO
    # Por defecto, el momento en que se dispara el cálculo.
    fecha_calibracion: Optional[datetime] = None
    observaciones: Optional[str] = None

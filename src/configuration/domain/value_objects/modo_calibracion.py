"""Value object ``ModoCalibracion`` — modalidad de una calibración (RF-24 v2.0)."""
from __future__ import annotations

from enum import Enum


class ModoCalibracion(str, Enum):
    """SENSOR = calibración manual con valor de referencia; VISION = línea base
    calculada por cámara.
    """
    # SENSOR: ajuste escalar de un sensor (`modulo9.calibraciones`, exige id_sensor).
    # VISION: línea base por área y especie (RFC-011, `modulo9.calibraciones_vision`).
    # Cada modalidad tiene su propio endpoint; cada DTO acepta solo la suya.
    SENSOR = "SENSOR"
    VISION = "VISION"

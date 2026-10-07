"""Value object ``ModoCalibracion`` — modalidad de una calibración (RF-24 v2.0)."""
from __future__ import annotations

from enum import Enum


class ModoCalibracion(str, Enum):
    # Solo SENSOR: `modulo9.calibraciones` exige id_sensor, así que toda fila es
    # una calibración de sensor y el modo se deriva sin columna propia. La línea
    # base por visión de RFC-011 se calibra por área y especie (sin sensor) y
    # entra como otro valor cuando exista su flujo; hasta entonces se rechaza.
    SENSOR = "SENSOR"

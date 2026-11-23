# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de consulta de parámetros de calibración de sensores."""
from abc import ABC, abstractmethod
from typing import Optional

from src.telemetry.domain.entities.telemetria import ParametrosCalibacion


class CalibracionPort(ABC):
    """Puerto para obtener la calibración vigente de un sensor."""

    @abstractmethod
    def obtener_parametros(
        self,
        sensor_id: int,
        id_dispositivo_iot: int,
    ) -> Optional[ParametrosCalibacion]:
        """Retorna parámetros de calibración (ganancia, offset) para el sensor.

        Retorna None si no existe calibración configurada para el sensor.
        """

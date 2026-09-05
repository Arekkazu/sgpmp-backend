from abc import ABC, abstractmethod
from typing import Optional

from src.telemetry.domain.entities.telemetria import ParametrosCalibacion


class CalibracionPort(ABC):

    @abstractmethod
    def obtener_parametros(
        self,
        sensor_id: int,
        id_dispositivo_iot: int,
    ) -> Optional[ParametrosCalibacion]:
        """Retorna parámetros de calibración (ganancia, offset) para el sensor.

        Retorna None si no existe calibración configurada para el sensor.
        """

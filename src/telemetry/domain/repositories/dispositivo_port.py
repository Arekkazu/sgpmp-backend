from abc import ABC, abstractmethod
from typing import Optional

from src.telemetry.domain.entities.telemetria import DispositivoInfo


class DispositivoPort(ABC):

    @abstractmethod
    def obtener_dispositivo_activo(
        self,
        device_id: int,
        sensor_id: int,
        access_key: str,
    ) -> Optional[DispositivoInfo]:
        """Valida identidad del dispositivo contra M09.

        Retorna DispositivoInfo si:
        - device_id existe en modulo9.dispositivos_iot y es_activo=True
        - sensor_id existe en modulo9.sensores, pertenece al device_id y es_activo=True
        - access_key coincide con el serial del dispositivo

        Retorna None si cualquier condición no se cumple.
        """

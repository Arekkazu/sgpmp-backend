from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from src.telemetry.domain.entities.telemetria import DispositivoInfo


@dataclass
class DispositivoHeartbeatInfo:
    id_dispositivo_iot: int
    id_infraestructura: int
    es_activo: bool


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

    @abstractmethod
    def validar_dispositivo_heartbeat(
        self,
        device_id: int,
        access_key: str,
    ) -> Optional[DispositivoHeartbeatInfo]:
        """Valida identidad del dispositivo para heartbeat (sin sensor específico).

        Retorna DispositivoHeartbeatInfo si device_id existe y access_key coincide con serial.
        Retorna None si no se encuentra o credenciales inválidas.
        """

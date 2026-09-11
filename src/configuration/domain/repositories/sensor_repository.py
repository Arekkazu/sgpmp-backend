"""Puerto (ABC) para persistencia de sensores (RF-22)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.sensor import Sensor


class SensorRepository(ABC):

    @abstractmethod
    def obtener_por_id(self, id_sensor: int) -> Optional[Sensor]:
        ...

    @abstractmethod
    def guardar(self, sensor: Sensor) -> Sensor:
        ...

    @abstractmethod
    def listar_por_dispositivo(self, id_dispositivo_iot: int) -> list[Sensor]:
        ...

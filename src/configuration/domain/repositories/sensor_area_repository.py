"""Puerto (ABC) para persistencia de asociaciones sensor-área (RF-22)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.sensor_area import SensorArea


class SensorAreaRepository(ABC):

    @abstractmethod
    def obtener_asociacion_activa(self, id_sensor: int) -> Optional[SensorArea]:
        """Retorna la asociación con tiene_estado=True, o None si no existe."""
        ...

    @abstractmethod
    def guardar(self, sensor_area: SensorArea) -> SensorArea:
        ...

    @abstractmethod
    def actualizar(self, sensor_area: SensorArea) -> SensorArea:
        ...

    @abstractmethod
    def listar_por_sensor(self, id_sensor: int) -> list[SensorArea]:
        """Retorna historial completo de asociaciones del sensor."""
        ...

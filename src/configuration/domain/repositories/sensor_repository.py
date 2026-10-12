"""Puerto (ABC) para persistencia de sensores (RF-22)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.sensor import Sensor


class SensorRepository(ABC):
    """Contrato de acceso a datos para :class:`Sensor`."""

    @abstractmethod
    def obtener_por_id(self, id_sensor: int) -> Optional[Sensor]:
        """Obtiene el sensor por id, o ``None`` si no existe."""
        ...

    @abstractmethod
    def guardar(self, sensor: Sensor) -> Sensor:
        """Inserta el sensor y devuelve la entidad con su id asignado."""
        ...

    @abstractmethod
    def listar_por_dispositivo(self, id_dispositivo_iot: int) -> list[Sensor]:
        """Sensores del dispositivo IoT."""
        ...

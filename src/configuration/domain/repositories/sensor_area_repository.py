"""Puerto (ABC) para persistencia de asociaciones sensor-área (RF-22)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.sensor_area import SensorArea


class SensorAreaRepository(ABC):
    """Contrato de acceso a datos para :class:`SensorArea`."""

    @abstractmethod
    def obtener_asociacion_activa(self, id_sensor: int) -> Optional[SensorArea]:
        """Retorna la asociación con tiene_estado=True, o None si no existe."""
        ...

    @abstractmethod
    def guardar(self, sensor_area: SensorArea) -> SensorArea:
        """Inserta la asociación sensor-área y devuelve la entidad con su id asignado."""
        ...

    @abstractmethod
    def actualizar(self, sensor_area: SensorArea) -> SensorArea:
        """Persiste los cambios de la asociación sensor-área y devuelve la entidad
        actualizada.
        """
        ...

    @abstractmethod
    def listar_por_sensor(self, id_sensor: int) -> list[SensorArea]:
        """Retorna historial completo de asociaciones del sensor."""
        ...

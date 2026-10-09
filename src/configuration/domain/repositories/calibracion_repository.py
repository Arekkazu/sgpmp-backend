"""Puerto (ABC) para persistencia de calibraciones de sensores (RF-24)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.configuration.domain.entities.calibracion import Calibracion


class CalibracionRepository(ABC):
    """Contrato de persistencia del historial de calibraciones."""

    @abstractmethod
    def guardar(self, calibracion: Calibracion) -> Calibracion:
        """Inserta la calibración y devuelve la entidad con su id asignado."""
        ...

    @abstractmethod
    def listar_por_sensor(self, id_sensor: int) -> list[Calibracion]:
        """Historial de calibraciones del sensor, de la más reciente a la más antigua.
        """
        ...

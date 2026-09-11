"""Puerto (ABC) para persistencia de calibraciones de sensores (RF-24)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.configuration.domain.entities.calibracion import Calibracion


class CalibracionRepository(ABC):

    @abstractmethod
    def guardar(self, calibracion: Calibracion) -> Calibracion:
        ...

    @abstractmethod
    def listar_por_sensor(self, id_sensor: int) -> list[Calibracion]:
        ...

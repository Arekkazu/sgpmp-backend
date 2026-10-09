from __future__ import annotations

import datetime
from abc import ABC, abstractmethod

from src.telemetry.domain.entities.observacion_vision import ObservacionVision


class ObservacionVisionRepository(ABC):

    @abstractmethod
    def fechas_existentes(
        self, id_dispositivo_iot: int, fechas: list[datetime.datetime]
    ) -> set[datetime.datetime]:
        """De ``fechas``, las que ya tienen observación de esa cámara (reenvío del buffer)."""

    @abstractmethod
    def guardar(self, observacion: ObservacionVision) -> ObservacionVision: ...

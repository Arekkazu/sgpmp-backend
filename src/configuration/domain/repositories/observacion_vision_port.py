"""Puerto ``ObservacionVisionPort`` — vectores de comportamiento de las cámaras (RF-53/RF-56).

Los produce M03 junto con su índice de calidad (RF-62) en
``modulo3.observaciones_vision``; el router inyecta ``ObservacionVisionM03Adapter``.
"""
from __future__ import annotations

import datetime
from abc import ABC, abstractmethod

from src.configuration.domain.entities.observacion_vision import ObservacionVision


class ObservacionVisionPort(ABC):

    @abstractmethod
    def listar(
        self,
        ids_dispositivos: list[int],
        inicio: datetime.datetime,
        fin: datetime.datetime,
    ) -> list[ObservacionVision]:
        """Observaciones de esas cámaras con fecha en [inicio, fin]."""
        raise NotImplementedError

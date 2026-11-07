# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-23 | Leandro | DEV-24 RF-24: permitir seleccionar observaciones del area solicitada. |
"""Puerto ``ObservacionVisionPort`` — vectores de comportamiento de las cámaras (RF-53/RF-56).

Los produce M03 junto con su índice de calidad (RF-62) en
``modulo3.observaciones_vision``; el router inyecta ``ObservacionVisionM03Adapter``.
"""
from __future__ import annotations

import datetime
from abc import ABC, abstractmethod

from src.configuration.domain.entities.observacion_vision import ObservacionVision


class ObservacionVisionPort(ABC):
    """Puerto hacia M03 para leer observaciones de visión de un conjunto de cámaras."""

    @abstractmethod
    def listar(
        self,
        ids_dispositivos: list[int],
        inicio: datetime.datetime,
        fin: datetime.datetime,
        *,
        id_infraestructura: int | None = None,
    ) -> list[ObservacionVision]:
        """Observaciones en [inicio, fin], limitadas al área cuando se informa su ID."""
        raise NotImplementedError

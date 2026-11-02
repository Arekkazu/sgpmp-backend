# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-66: cámaras de visión de un área (para ver sus capturas)      |
from __future__ import annotations

from abc import ABC, abstractmethod


class CamarasAreaPort(ABC):

    @abstractmethod
    def camaras(self, id_area: int) -> list[int]:
        """Cámaras del área que el usuario puede ver (RLS de M09): vacía si el área no es suya."""

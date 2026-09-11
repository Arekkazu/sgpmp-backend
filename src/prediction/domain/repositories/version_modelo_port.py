from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class VersionModeloPort(ABC):
    @abstractmethod
    def obtener_estado(self, id_version: int) -> Optional[str]:
        """Devuelve el estado_version del modelo o None si no existe."""
        ...

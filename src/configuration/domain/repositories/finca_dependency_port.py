"""Puerto para verificar dependencias activas de una finca antes de desactivarla (RF-19 FA-04)."""
from __future__ import annotations

from abc import ABC, abstractmethod


class FincaDependencyPort(ABC):

    @abstractmethod
    def tiene_dependencias_activas(self, id_finca: int) -> bool:
        """Retorna True si la finca tiene dispositivos IoT o activos biológicos activos."""
        raise NotImplementedError

"""Puerto para verificar dependencias activas de un área antes de desactivarla (RF-20 FA-04)."""
from __future__ import annotations

from abc import ABC, abstractmethod


class InfraestructuraDependencyPort(ABC):

    @abstractmethod
    def tiene_dependencias_activas(self, id_infraestructura: int) -> bool:
        """Retorna True si el área tiene dispositivos IoT o activos biológicos activos."""
        raise NotImplementedError

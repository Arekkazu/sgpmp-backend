"""Puerto para notificar al módulo de monitoreo IoT (RF-18, paso 05 DFD)."""
from __future__ import annotations

from abc import ABC, abstractmethod


class IotNotificacionPort(ABC):

    @abstractmethod
    def notificar_configuracion(self, *, frecuencia_muestreo: int, heartbeat: int) -> None:
        """Notifica la configuración operativa activa al módulo de monitoreo IoT."""
        raise NotImplementedError

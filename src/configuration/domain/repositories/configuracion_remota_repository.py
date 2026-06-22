"""Puerto (ABC) para persistencia de configuraciones remotas de dispositivos IoT (RF-23)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.configuracion_remota import ConfiguracionRemota


class ConfiguracionRemotaRepository(ABC):

    @abstractmethod
    def guardar(self, config: ConfiguracionRemota) -> ConfiguracionRemota:
        ...

    @abstractmethod
    def obtener_pendiente(self, id_dispositivo_iot: int) -> Optional[ConfiguracionRemota]:
        """Retorna la configuración con estado='PENDIENTE' si existe, o None."""
        ...

    @abstractmethod
    def listar_por_dispositivo(self, id_dispositivo_iot: int) -> list[ConfiguracionRemota]:
        ...

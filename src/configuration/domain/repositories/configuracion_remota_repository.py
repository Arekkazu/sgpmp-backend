"""Puerto (ABC) para persistencia de configuraciones remotas de dispositivos IoT (RF-23)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.configuracion_remota import ConfiguracionRemota


class ConfiguracionRemotaRepository(ABC):
    """Contrato de acceso a datos para :class:`ConfiguracionRemota`."""

    @abstractmethod
    def guardar(self, config: ConfiguracionRemota) -> ConfiguracionRemota:
        """Inserta la configuración remota y devuelve la entidad con su id asignado."""
        ...

    @abstractmethod
    def actualizar(self, config: ConfiguracionRemota) -> ConfiguracionRemota:
        """Persiste los cambios de la configuración remota y devuelve la entidad
        actualizada.
        """
        ...

    @abstractmethod
    def obtener_por_id(self, id_configuracion_remota: int) -> Optional[ConfiguracionRemota]:
        """Obtiene la configuración remota por id, o ``None`` si no existe."""
        ...

    @abstractmethod
    def obtener_pendiente(self, id_dispositivo_iot: int) -> Optional[ConfiguracionRemota]:
        """Retorna la configuración con estado='PENDIENTE' si existe, o None."""
        ...

    @abstractmethod
    def listar_por_dispositivo(self, id_dispositivo_iot: int) -> list[ConfiguracionRemota]:
        """Historial de configuraciones remotas del dispositivo."""
        ...

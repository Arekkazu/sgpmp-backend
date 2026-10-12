"""Puerto de persistencia del agregado ``ConfiguracionGlobal`` (RF-18)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.configuracion_global import ConfiguracionGlobal


class ConfiguracionGlobalRepository(ABC):
    """Contrato de acceso a datos para :class:`ConfiguracionGlobal`."""

    @abstractmethod
    def obtener_activo(self) -> Optional[ConfiguracionGlobal]:
        """Obtiene la configuración global activa, o ``None`` si no hay ninguna."""
        raise NotImplementedError

    @abstractmethod
    def obtener_por_id(
        self, id_configuracion_global: int, *, bloquear: bool = False
    ) -> Optional[ConfiguracionGlobal]:
        """``bloquear=True`` toma la fila con ``SELECT ... FOR UPDATE`` (#498)."""
        raise NotImplementedError

    @abstractmethod
    def guardar(self, config: ConfiguracionGlobal) -> ConfiguracionGlobal:
        """Inserta la configuración global y devuelve la entidad con su id asignado."""
        raise NotImplementedError

    @abstractmethod
    def actualizar(self, config: ConfiguracionGlobal) -> ConfiguracionGlobal:
        """Persiste los cambios de la configuración global y devuelve la entidad
        actualizada.
        """
        raise NotImplementedError

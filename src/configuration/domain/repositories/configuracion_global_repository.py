"""Puerto de persistencia del agregado ``ConfiguracionGlobal`` (RF-18)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.configuracion_global import ConfiguracionGlobal


class ConfiguracionGlobalRepository(ABC):

    @abstractmethod
    def obtener_activo(self) -> Optional[ConfiguracionGlobal]:
        raise NotImplementedError

    @abstractmethod
    def obtener_por_id(self, id_configuracion_global: int) -> Optional[ConfiguracionGlobal]:
        raise NotImplementedError

    @abstractmethod
    def guardar(self, config: ConfiguracionGlobal) -> ConfiguracionGlobal:
        raise NotImplementedError

    @abstractmethod
    def actualizar(self, config: ConfiguracionGlobal) -> ConfiguracionGlobal:
        raise NotImplementedError

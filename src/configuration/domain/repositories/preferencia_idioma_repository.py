"""Puerto de persistencia del agregado ``PreferenciaIdioma`` (RF-29)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.preferencia_idioma import PreferenciaIdioma


class PreferenciaIdiomaRepository(ABC):

    @abstractmethod
    def obtener_por_usuario(self, id_usuario: int) -> Optional[PreferenciaIdioma]:
        raise NotImplementedError

    @abstractmethod
    def obtener_global(self) -> Optional[PreferenciaIdioma]:
        raise NotImplementedError

    @abstractmethod
    def version_perfil(self, id_usuario: int) -> Optional[int]:
        """Versión actual del perfil del usuario, para la comprobación de concurrencia."""
        raise NotImplementedError

    @abstractmethod
    def guardar(self, entidad: PreferenciaIdioma) -> PreferenciaIdioma:
        raise NotImplementedError

    @abstractmethod
    def actualizar(self, entidad: PreferenciaIdioma) -> PreferenciaIdioma:
        raise NotImplementedError

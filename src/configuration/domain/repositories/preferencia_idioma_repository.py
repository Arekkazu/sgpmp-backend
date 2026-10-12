"""Puerto de persistencia del agregado ``PreferenciaIdioma`` (RF-29)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.preferencia_idioma import PreferenciaIdioma


class PreferenciaIdiomaRepository(ABC):
    """Contrato de acceso a datos para :class:`PreferenciaIdioma`."""

    @abstractmethod
    def obtener_por_usuario(self, id_usuario: int) -> Optional[PreferenciaIdioma]:
        """Obtiene la preferencia de idioma personal del usuario, o ``None`` si no
        tiene.
        """
        raise NotImplementedError

    @abstractmethod
    def obtener_global(self) -> Optional[PreferenciaIdioma]:
        """Obtiene la preferencia de idioma global del sistema, o ``None`` si no está
        definido.
        """
        raise NotImplementedError

    @abstractmethod
    def version_perfil(self, id_usuario: int) -> Optional[int]:
        """Versión actual del perfil del usuario, para la comprobación de concurrencia."""
        raise NotImplementedError

    @abstractmethod
    def guardar(self, entidad: PreferenciaIdioma) -> PreferenciaIdioma:
        """Inserta la preferencia de idioma y devuelve la entidad con su id asignado."""
        raise NotImplementedError

    @abstractmethod
    def actualizar(self, entidad: PreferenciaIdioma) -> PreferenciaIdioma:
        """Persiste los cambios de la preferencia de idioma y devuelve la entidad
        actualizada.
        """
        raise NotImplementedError

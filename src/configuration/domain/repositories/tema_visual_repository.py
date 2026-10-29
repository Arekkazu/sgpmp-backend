"""Puerto de persistencia del agregado ``TemaVisual`` (RF-27)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.tema_visual import TemaVisual


class TemaVisualRepository(ABC):
    """Contrato de acceso a datos para :class:`TemaVisual`."""

    @abstractmethod
    def obtener_por_usuario(self, id_usuario: int) -> Optional[TemaVisual]:
        """Obtiene el tema visual personal del usuario, o ``None`` si no tiene."""
        raise NotImplementedError

    @abstractmethod
    def obtener_global(self) -> Optional[TemaVisual]:
        """Obtiene el tema visual global del sistema, o ``None`` si no está definido."""
        raise NotImplementedError

    @abstractmethod
    def guardar(self, entidad: TemaVisual) -> TemaVisual:
        """Inserta el tema visual y devuelve la entidad con su id asignado."""
        raise NotImplementedError

    @abstractmethod
    def actualizar(self, entidad: TemaVisual) -> TemaVisual:
        """Persiste los cambios del tema visual y devuelve la entidad actualizada.
        """
        raise NotImplementedError

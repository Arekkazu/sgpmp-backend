"""Puerto de persistencia del agregado ``IdentidadVisual`` (RF-26)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.identidad_visual import IdentidadVisual


class IdentidadVisualRepository(ABC):
    """Contrato de acceso a datos para :class:`IdentidadVisual`."""

    @abstractmethod
    def obtener_por_finca(self, id_finca: int, *, bloquear: bool = False) -> Optional[IdentidadVisual]:
        """``bloquear=True`` toma la fila con ``SELECT ... FOR UPDATE`` (#498)."""
        raise NotImplementedError

    @abstractmethod
    def guardar(self, entidad: IdentidadVisual) -> IdentidadVisual:
        """Inserta una versión nueva de la identidad visual."""
        raise NotImplementedError

    @abstractmethod
    def actualizar(self, entidad: IdentidadVisual) -> IdentidadVisual:
        """Persiste los cambios de la identidad visual y devuelve la entidad
        actualizada.
        """
        raise NotImplementedError

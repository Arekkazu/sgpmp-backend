"""Puerto de persistencia del agregado ``IdentidadVisual`` (RF-26)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.identidad_visual import IdentidadVisual


class IdentidadVisualRepository(ABC):

    @abstractmethod
    def obtener_por_finca(self, id_finca: int) -> Optional[IdentidadVisual]:
        raise NotImplementedError

    @abstractmethod
    def guardar(self, entidad: IdentidadVisual) -> IdentidadVisual:
        raise NotImplementedError

    @abstractmethod
    def actualizar(self, entidad: IdentidadVisual) -> IdentidadVisual:
        raise NotImplementedError

"""Puerto de persistencia del agregado ``TemaVisual`` (RF-27)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.tema_visual import TemaVisual


class TemaVisualRepository(ABC):

    @abstractmethod
    def obtener_por_usuario(self, id_usuario: int) -> Optional[TemaVisual]:
        raise NotImplementedError

    @abstractmethod
    def obtener_global(self) -> Optional[TemaVisual]:
        raise NotImplementedError

    @abstractmethod
    def guardar(self, entidad: TemaVisual) -> TemaVisual:
        raise NotImplementedError

    @abstractmethod
    def actualizar(self, entidad: TemaVisual) -> TemaVisual:
        raise NotImplementedError

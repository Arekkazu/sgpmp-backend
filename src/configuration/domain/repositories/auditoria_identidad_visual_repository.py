"""Puerto de auditoría para cambios en la identidad visual (RF-26)."""
from __future__ import annotations

from abc import ABC, abstractmethod


class AuditoriaIdentidadVisualRepository(ABC):

    @abstractmethod
    def registrar(
        self,
        *,
        id_usuario: int,
        valor_anterior: dict,
        valor_nuevo: dict,
    ) -> None:
        raise NotImplementedError

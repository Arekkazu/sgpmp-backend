"""Puerto de auditoría para cambios en la identidad visual (RF-26)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.configuration.domain.entities.auditoria_identidad_visual import AuditoriaIdentidadVisual


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

    @abstractmethod
    def listar_por_finca(self, id_finca: int) -> list[AuditoriaIdentidadVisual]:
        """Lista el historial canónico de una finca, más reciente primero."""
        raise NotImplementedError

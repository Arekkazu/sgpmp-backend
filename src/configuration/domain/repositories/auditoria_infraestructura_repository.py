"""Puerto de auditoría para ``Infraestructura`` (RF-20)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class AuditoriaInfraestructuraRepository(ABC):

    @abstractmethod
    def registrar(
        self,
        *,
        id_infraestructura: int,
        id_usuario: int,
        tipo_operacion: str,
        valores_nuevos: dict[str, Any],
        valores_anteriores: Optional[dict[str, Any]] = None,
    ) -> None:
        raise NotImplementedError

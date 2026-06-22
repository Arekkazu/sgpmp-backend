"""Puerto de auditoría para ``ConfiguracionGlobal`` (RF-18)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class AuditoriaConfigRepository(ABC):

    @abstractmethod
    def registrar(
        self,
        *,
        id_configuracion_global: int,
        id_usuario: int,
        tipo_operacion: str,
        valores_nuevos: dict[str, Any],
        valores_anteriores: Optional[dict[str, Any]] = None,
    ) -> None:
        raise NotImplementedError

"""Puerto de auditoría de etapas del ciclo productivo (capa de dominio)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class AuditoriaCicloRepository(ABC):

    @abstractmethod
    def registrar(
        self,
        *,
        id_ciclo_biologico: int,
        id_usuario: int,
        tipo_operacion: str,
        valores_nuevos: dict[str, Any],
        valores_anteriores: Optional[dict[str, Any]] = None,
    ) -> None:
        """Inserta un registro de auditoría append-only. Hace ``flush``."""
        raise NotImplementedError

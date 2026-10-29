"""Puerto de auditoría para el agregado ``Finca`` (RF-19)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class AuditoriaFincaRepository(ABC):
    """Contrato de la auditoría de fincas."""

    @abstractmethod
    def registrar(
        self,
        *,
        id_finca: int,
        id_usuario: int,
        tipo_operacion: str,
        valores_nuevos: dict[str, Any],
        valores_anteriores: Optional[dict[str, Any]] = None,
    ) -> None:
        """Inserta un registro de auditoría inmutable sobre la finca con los valores
        antes/después.
        """
        raise NotImplementedError

"""Puerto (ABC) para auditoría de asociaciones sensor-área."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class AuditoriaSensorAreaRepository(ABC):

    @abstractmethod
    def registrar(
        self,
        *,
        id_sensores_area_asociada: int,
        id_usuario: int,
        tipo_operacion: str,
        valores_nuevos: dict,
        valores_anteriores: Optional[dict] = None,
    ) -> None:
        ...

"""Puerto (ABC) para auditoría inmutable de calibraciones (RF-24 / RF-10)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class AuditoriaCalibracionRepository(ABC):

    @abstractmethod
    def registrar(
        self,
        *,
        id_calibracion: int,
        id_usuario: int,
        tipo_operacion: str,
        valores_nuevos: dict,
        valores_anteriores: Optional[dict] = None,
    ) -> None:
        ...

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.prediction.domain.entities.distribucion_ota import DistribucionOta


class DistribucionOtaRepository(ABC):
    """``modulo4.distribuciones_ota`` (DB-04, DEV-15)."""

    @abstractmethod
    def guardar(self, entidad: DistribucionOta) -> DistribucionOta: ...

    @abstractmethod
    def obtener_por_id(self, id_distribucion: int, *, bloquear: bool = False) -> Optional[DistribucionOta]: ...

    @abstractmethod
    def actualizar(self, entidad: DistribucionOta) -> DistribucionOta: ...

"""Puerto de persistencia del agregado ``DashboardLayout`` (RF-28)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.dashboard_layout import DashboardLayout


class DashboardLayoutRepository(ABC):

    @abstractmethod
    def obtener_por_usuario(self, id_usuario: int) -> Optional[DashboardLayout]:
        raise NotImplementedError

    @abstractmethod
    def guardar(self, entidad: DashboardLayout) -> DashboardLayout:
        raise NotImplementedError

    @abstractmethod
    def actualizar(self, entidad: DashboardLayout) -> DashboardLayout:
        raise NotImplementedError

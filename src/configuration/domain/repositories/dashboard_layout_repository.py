"""Puerto de persistencia del agregado ``DashboardLayout`` (RF-28)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.dashboard_layout import DashboardLayout


class DashboardLayoutRepository(ABC):
    """Contrato de acceso a datos para :class:`DashboardLayout`."""

    @abstractmethod
    def obtener_por_usuario(self, id_usuario: int) -> Optional[DashboardLayout]:
        """Obtiene el dashboard guardado del usuario, o ``None`` si nunca lo
        personalizó.
        """
        raise NotImplementedError

    @abstractmethod
    def obtener_default_de_rol(self, id_usuario: int, id_rol: int) -> Optional[DashboardLayout]:
        """Layout predeterminado del rol, o ``None`` si el rol no tiene uno definido."""
        raise NotImplementedError

    @abstractmethod
    def nombre_de_rol(self, id_rol: int) -> Optional[str]:
        """Nombre legible del rol, para el mensaje de fallo de restauración."""
        raise NotImplementedError

    @abstractmethod
    def version_perfil(self, id_usuario: int) -> Optional[int]:
        """Versión actual del perfil del usuario, para detectar edición concurrente."""
        raise NotImplementedError

    @abstractmethod
    def guardar(self, entidad: DashboardLayout) -> DashboardLayout:
        """Inserta el dashboard y devuelve la entidad con su id asignado."""
        raise NotImplementedError

    @abstractmethod
    def actualizar(self, entidad: DashboardLayout) -> DashboardLayout:
        """Persiste los cambios del dashboard y devuelve la entidad actualizada."""
        raise NotImplementedError

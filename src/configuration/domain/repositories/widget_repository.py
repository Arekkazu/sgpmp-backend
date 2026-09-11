"""Puerto de consulta del catálogo de widgets del dashboard (RF-28)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.configuration.domain.entities.widget import Widget


class WidgetRepository(ABC):

    @abstractmethod
    def obtener_activos(self) -> list[Widget]:
        """Todos los widgets habilitados del catálogo, sin filtrar por rol."""
        raise NotImplementedError

    @abstractmethod
    def ids_legibles_por_rol(self, id_rol: int) -> set[int]:
        """Ids de widgets cuyo recurso el rol puede leer, según ``modulo1.permisos``."""
        raise NotImplementedError

"""Puerto de persistencia del agregado ``TipoArea`` (capa de dominio, RF-20).

La implementación concreta vive en
``infrastructure/repositories/tipo_area_repository.py``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.tipo_area import TipoArea


class TipoAreaRepository(ABC):
    """Contrato de acceso a datos para el agregado :class:`TipoArea`."""

    @abstractmethod
    def obtener_por_id(self, id_tipo_area: int) -> Optional[TipoArea]:
        raise NotImplementedError

    @abstractmethod
    def obtener_por_nombre(self, nombre: str) -> Optional[TipoArea]:
        """Busca un tipo de área cuyo nombre coincida (case-insensitive)."""
        raise NotImplementedError

    @abstractmethod
    def guardar(self, tipo_area: TipoArea) -> TipoArea:
        raise NotImplementedError

    @abstractmethod
    def actualizar(self, tipo_area: TipoArea) -> TipoArea:
        raise NotImplementedError

    @abstractmethod
    def listar(self, *, solo_activos: bool = False) -> list[TipoArea]:
        """Retorna el catálogo, ordenado por nombre."""
        raise NotImplementedError

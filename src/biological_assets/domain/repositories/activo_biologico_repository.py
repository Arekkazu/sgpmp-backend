from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico, HistorialInfraestructura


class ActivoBiologicoRepository(ABC):
    @abstractmethod
    def guardar(self, activo: ActivoBiologico) -> ActivoBiologico:
        """Persiste el activo biológico y sus detalles en una sola transacción de DB."""

    @abstractmethod
    def obtener_por_id(self, id_activo: int) -> Optional[ActivoBiologico]:
        """Retorna el activo biológico con sus detalles, o None si no existe."""

    @abstractmethod
    def existe_identificador(self, identificador: str) -> bool:
        """Verifica si el identificador ya está registrado (case-insensitive)."""

    @abstractmethod
    def obtener_asociacion_activa(self, id_activo: int) -> Optional[HistorialInfraestructura]:
        """Retorna la asociación de infraestructura activa (fecha_fin IS NULL)."""

    @abstractmethod
    def obtener_historial_infraestructura(self, id_activo: int) -> list[HistorialInfraestructura]:
        """Retorna el historial completo de asociaciones de infraestructura."""

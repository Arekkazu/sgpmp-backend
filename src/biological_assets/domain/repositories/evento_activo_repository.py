from __future__ import annotations

from abc import ABC, abstractmethod

from src.biological_assets.domain.entities.activo_biologico import EventoActivo


class EventoActivoRepository(ABC):
    @abstractmethod
    def guardar(self, evento: EventoActivo) -> EventoActivo:
        """Persiste evento_activo y su subtipo en una sola unidad de trabajo (flush)."""

    @abstractmethod
    def listar_por_activo(self, id_activo: int) -> list[EventoActivo]:
        """Retorna todos los eventos del activo ordenados por fecha DESC."""

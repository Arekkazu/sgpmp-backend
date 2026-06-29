from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.biological_assets.domain.entities.activo_biologico import EventoActivo


class EventoActivoRepository(ABC):
    @abstractmethod
    def guardar(self, evento: EventoActivo) -> EventoActivo:
        """Persiste evento_activo y su subtipo en una sola unidad de trabajo (flush)."""

    @abstractmethod
    def listar_por_activo(self, id_activo: int) -> list[EventoActivo]:
        """Retorna todos los eventos del activo ordenados por fecha DESC."""

    @abstractmethod
    def obtener_ultima_fecha(self, id_activo: int) -> Optional[datetime]:
        """Retorna la fecha del evento más reciente del activo, o None si no tiene eventos."""

    @abstractmethod
    def tiene_diagnostico_previo(self, id_activo: int) -> bool:
        """Retorna True si el activo tiene al menos un evento DIAGNOSTICO registrado."""

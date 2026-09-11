from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
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

    @abstractmethod
    def tiene_servicio_o_inseminacion_previa(self, id_activo: int) -> bool:
        """Retorna True si el activo tiene al menos un evento reproductivo de tipo servicio o inseminacion."""

    @abstractmethod
    def tiene_diagnostico_positivo_previo(self, id_activo: int) -> bool:
        """Retorna True si el activo tiene al menos un evento reproductivo de diagnostico con resultado exitoso."""

    @abstractmethod
    def existe_productivo_duplicado(self, id_activo: int, id_metrica_produccion: int, fecha: date) -> bool:
        """Retorna True si ya existe un evento productivo del mismo tipo para el mismo activo en la misma fecha."""

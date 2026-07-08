from abc import ABC, abstractmethod

from src.telemetry.domain.entities.telemetria import EventoEdgeComputing


class EventoEdgeRepository(ABC):
    @abstractmethod
    def guardar(self, evento: EventoEdgeComputing) -> EventoEdgeComputing: ...

# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, puerto y método |
"""Puerto de dominio para persistir eventos procesados en el Edge.

La aplicación depende de esta interfaz, no del repositorio SQLAlchemy. Recibe
y devuelve entidades de dominio (:class:`EventoEdgeComputing`).
"""
from abc import ABC, abstractmethod

from src.telemetry.domain.entities.telemetria import EventoEdgeComputing


class EventoEdgeRepository(ABC):
    """Contrato de persistencia de eventos de inferencia/agregación del Edge."""

    @abstractmethod
    def guardar(self, evento: EventoEdgeComputing) -> EventoEdgeComputing:
        """Persiste un evento del Edge y devuelve la entidad resultante."""
        ...

# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, puerto y método |
"""Puerto de dominio para persistir los heartbeats de los dispositivos IoT.

La aplicación depende de esta interfaz; la infraestructura la implementa con
SQLAlchemy y mapea ORM ↔ entidad.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.telemetry.domain.entities.heartbeat import Heartbeat


class HeartbeatRepository(ABC):
    """Contrato de persistencia de los reportes de heartbeat."""

    @abstractmethod
    def guardar(self, heartbeat: Heartbeat) -> Heartbeat:
        """Persiste un heartbeat y devuelve la entidad con su identificador."""
        ...

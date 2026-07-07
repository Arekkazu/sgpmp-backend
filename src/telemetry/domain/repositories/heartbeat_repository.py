from __future__ import annotations

from abc import ABC, abstractmethod

from src.telemetry.domain.entities.heartbeat import Heartbeat


class HeartbeatRepository(ABC):

    @abstractmethod
    def guardar(self, heartbeat: Heartbeat) -> Heartbeat: ...

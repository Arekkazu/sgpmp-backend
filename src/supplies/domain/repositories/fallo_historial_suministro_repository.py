"""Puerto de fallos persistentes del motor async de historial de suministros (RF-81)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.supplies.domain.entities.trabajo_historial_suministro import FalloHistorialSuministro


class FalloHistorialSuministroRepository(ABC):
    @abstractmethod
    def registrar(self, fallo: FalloHistorialSuministro) -> FalloHistorialSuministro:
        raise NotImplementedError

    @abstractmethod
    def listar_no_resueltos(self) -> list[FalloHistorialSuministro]:
        raise NotImplementedError

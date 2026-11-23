# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de fallos persistentes del motor async de historial de suministros (RF-81)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.supplies.domain.entities.trabajo_historial_suministro import FalloHistorialSuministro


class FalloHistorialSuministroRepository(ABC):
    """Puerto de persistencia de fallos del historial asíncrono."""
    @abstractmethod
    def registrar(self, fallo: FalloHistorialSuministro) -> FalloHistorialSuministro:
        """Registra el fallo."""
        raise NotImplementedError

    @abstractmethod
    def listar_no_resueltos(self) -> list[FalloHistorialSuministro]:
        """Lista los fallos sin resolver."""
        raise NotImplementedError

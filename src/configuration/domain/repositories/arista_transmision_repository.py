# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RFC-021 RF-110 C21.1: puerto de las aristas de transmisión       |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de persistencia de aristas de transmisión."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.arista_transmision import AristaTransmision


class AristaTransmisionRepository(ABC):
    """Puerto de persistencia de aristas de transmisión."""

    @abstractmethod
    def guardar(self, arista: AristaTransmision) -> AristaTransmision:
        """409 si ya hay una arista activa con el mismo origen, destino y vía."""

    @abstractmethod
    def obtener_por_id(self, id_arista: int) -> Optional[AristaTransmision]:
        """Devuelve la arista, o ``None``."""
        ...

    @abstractmethod
    def actualizar(self, arista: AristaTransmision) -> AristaTransmision:
        """Actualiza la arista."""
        ...

    @abstractmethod
    def listar_activas_por_finca(self, id_finca: int) -> list[AristaTransmision]:
        """Lista las aristas activas de la finca."""
        ...

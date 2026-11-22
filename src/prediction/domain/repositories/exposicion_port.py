# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RFC-021 C21.4: focos vecinos y lotes expuestos según la topología de RF-110 |
"""Lo que RF-68 necesita de la topología sanitaria (RF-110) para la exposición entre áreas."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from src.prediction.domain.entities.riesgo_contagio import FocoVecino


class ExposicionPort(ABC):

    @abstractmethod
    def focos_hacia(self, id_lote: int, desde: datetime) -> list[FocoVecino]:
        """Áreas con arista activa hacia el área del lote cuyo último contagio desde ``desde`` tiene Fs > 0
        y confianza normal (RFC-021: solo propagan focos con ``confianza_baja = false``)."""

    @abstractmethod
    def lotes_expuestos(self, id_lote: int) -> list[int]:
        """Activos vivos de las áreas a las que llega una arista activa desde el área del lote."""

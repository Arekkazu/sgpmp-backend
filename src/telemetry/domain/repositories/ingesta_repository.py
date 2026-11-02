# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-02 | Arekkazu | AJF-07 RF-53: puerto de lectura del monitor de ingesta |
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.telemetry.domain.entities.lectura_ingesta import FiltrosIngesta, IndicadoresIngesta, LecturaIngesta


class IngestaRepository(ABC):

    @abstractmethod
    def listar(self, filtros: FiltrosIngesta) -> tuple[list[LecturaIngesta], int]:
        """Más recientes primero, paginado en BD; ``ids_fincas`` None = alcance global."""

    @abstractmethod
    def indicadores(self, desde: datetime, hasta: datetime, ids_fincas: Optional[list[int]]) -> IndicadoresIngesta:
        ...

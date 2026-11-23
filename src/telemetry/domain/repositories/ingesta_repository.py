# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-02 | Arekkazu | AJF-07 RF-53: puerto de lectura del monitor de ingesta |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de consulta de la bitácora de ingesta."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.telemetry.domain.entities.lectura_ingesta import FiltrosIngesta, IndicadoresIngesta, LecturaIngesta


class IngestaRepository(ABC):
    """Puerto del listado e indicadores de la bitácora de ingesta."""

    @abstractmethod
    def listar(self, filtros: FiltrosIngesta) -> tuple[list[LecturaIngesta], int]:
        """Más recientes primero, paginado en BD; ``ids_fincas`` None = alcance global."""

    @abstractmethod
    def indicadores(self, desde: datetime, hasta: datetime, ids_fincas: Optional[list[int]]) -> IndicadoresIngesta:
        """Calcula los indicadores de ingesta del rango y alcance dados."""
        ...

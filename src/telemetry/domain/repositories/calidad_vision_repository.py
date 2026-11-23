# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-03 | Arekkazu | RF-62: listado de observaciones de visión evaluadas (el panel mostraba datos de ejemplo) |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puertos del listado de calidad de visión y de su política vigente."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.telemetry.domain.entities.calidad_vision_listado import (
    FiltrosCalidadVision, ObservacionVisionEvaluada, PoliticaVisionVigente,
)


class CalidadVisionRepository(ABC):
    """Puerto de consulta de observaciones de visión evaluadas."""

    @abstractmethod
    def listar(self, filtros: FiltrosCalidadVision) -> tuple[list[ObservacionVisionEvaluada], int]:
        """Una página de observaciones (más recientes primero) y el total con el filtro."""


class PoliticaVisionPort(ABC):
    """Puerto para leer la política de calidad de visión vigente."""

    @abstractmethod
    def vigente(self) -> tuple[Optional[PoliticaVisionVigente], Optional[str]]:
        """(política, None) o (None, motivo) si en M09 falta o es inválida; nunca valores por defecto."""

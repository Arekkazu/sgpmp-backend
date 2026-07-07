from abc import ABC, abstractmethod

from src.telemetry.domain.entities.monitoreo import FiltrosHistorial, LecturaHistorica, ResumenEstadistico


class HistorialTelemetriaRepository(ABC):

    @abstractmethod
    def consultar(
        self, filtros: FiltrosHistorial
    ) -> tuple[list[LecturaHistorica], int]:
        """Devuelve (lecturas_paginadas, total_sin_paginar)."""

    @abstractmethod
    def calcular_estadisticas(self, filtros: FiltrosHistorial) -> list[ResumenEstadistico]:
        """Devuelve estadísticas por variable para el conjunto de filtros aplicado."""

# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-38 RF-59: zona horaria, truncado con aviso, bitácora y vacíos temporales |
from abc import ABC, abstractmethod

from src.telemetry.domain.entities.monitoreo import (
    FiltrosHistorial,
    LecturaHistorica,
    ResumenEstadistico,
    VacioTemporal,
)


class HistorialTelemetriaRepository(ABC):

    @abstractmethod
    def consultar(
        self, filtros: FiltrosHistorial
    ) -> tuple[list[LecturaHistorica], int]:
        """Devuelve (lecturas_paginadas, total_sin_paginar)."""

    @abstractmethod
    def calcular_estadisticas(self, filtros: FiltrosHistorial) -> list[ResumenEstadistico]:
        """Devuelve estadísticas por variable para el conjunto de filtros aplicado."""

    @abstractmethod
    def detectar_vacios(self, filtros: FiltrosHistorial) -> list[VacioTemporal]:
        """RF-59 E7 / CA-17: intervalos entre lecturas consecutivas del mismo sensor y
        variable mayores que 3 × su frecuencia de muestreo, en todo el rango filtrado."""

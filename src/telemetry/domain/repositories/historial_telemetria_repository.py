# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-38 RF-59: zona horaria, truncado con aviso, bitácora y vacíos temporales |
# | 2026-10-26 | Arekkazu | INC-M03 lote 26-10 RF-59: alertas correlacionadas y validación de variables |
from abc import ABC, abstractmethod

from src.telemetry.domain.entities.monitoreo import (
    AlertaCorrelacionada,
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

    @abstractmethod
    def alertas_correlacionadas(self, filtros: FiltrosHistorial) -> list[AlertaCorrelacionada]:
        """RF-59 Salida 5 / CA-8: alertas de RF-57 ligadas a las lecturas que cumplen los filtros."""

    @abstractmethod
    def variables_no_reconocidas(self, tipos: list[str]) -> list[str]:
        """Los valores de ``tipo_variable`` que no son código ni nombre de una variable del catálogo."""

# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-81 R10: consulta con tiempo límite     |
"""Puerto de lectura del historial de suministros (RF-81).

Fuente: ``modulo5.registro_suministro`` (ledger poblado desde RF-75/76). Es de
solo lectura; no muta ningún dato.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.supplies.domain.entities.historial_suministro import (
    FiltrosHistorialSuministro,
    ResultadoHistorialSuministro,
)


class ConsultaExcedioTiempo(Exception):
    """La consulta síncrona superó su tiempo límite (RF-81 R10): pasa a modo asíncrono."""


class HistorialSuministroReadPort(ABC):
    @abstractmethod
    def contar_total_activo(self, id_activo_biologico: int) -> int:
        """Volumen histórico total del activo (ignora filtros de página), para
        determinar el nivel de volumen (Restricción 11 de RF-81)."""
        raise NotImplementedError

    @abstractmethod
    def consultar(
        self,
        filtros: FiltrosHistorialSuministro,
        ids_activos_permitidos: Optional[list[int]],
        tiempo_limite_segundos: Optional[int] = None,
    ) -> ResultadoHistorialSuministro:
        """Página filtrada + agregados sobre el conjunto completo filtrado.

        ``ids_activos_permitidos`` es ``None`` cuando el rol no tiene
        restricción de alcance; una lista (posiblemente vacía) cuando sí.
        Con ``tiempo_limite_segundos`` lanza :class:`ConsultaExcedioTiempo` si no termina a tiempo.
        """
        raise NotImplementedError

    @abstractmethod
    def ciclo_pertenece_a_activo(self, id_activo_biologico: int, id_ciclo_productivo: int) -> bool:
        """Restricción 7(c) de RF-81: valida la combinación de filtros ciclo/activo."""
        raise NotImplementedError

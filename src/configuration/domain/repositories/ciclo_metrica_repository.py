"""Puerto de la relación métrica ↔ ciclo productivo (``modulo9.metricas_ciclo_productivo``).

RF-43 E-04 exige que el producto de un evento productivo esté habilitado para el
ciclo de la fase activa, pero ninguna pantalla permitía configurarlo: la tabla
solo se llenaba por SQL.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.configuration.domain.entities.ciclo_metrica import CicloMetrica


class CicloMetricaRepository(ABC):
    """Ciclos productivos de una especie y cuáles habilitan cada métrica."""

    @abstractmethod
    def listar_por_metrica(self, id_metrica_produccion: int, id_especie: int) -> list[CicloMetrica]:
        """Ciclos productivos de la especie, ordenados por nombre, con ``habilitada`` para la métrica."""

    @abstractmethod
    def reemplazar(self, id_metrica_produccion: int, ids_ciclos_productivos: set[int]) -> None:
        """Deja la métrica habilitada exactamente en esos ciclos."""

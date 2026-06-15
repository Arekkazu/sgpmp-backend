"""Puerto de persistencia del agregado ``MetricaProduccion`` (capa de dominio).

Define el contrato que la capa de aplicación usa para leer y guardar métricas
de producción por especie (RF-16).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.metrica_produccion import MetricaProduccion
from src.configuration.domain.value_objects.nombre_metrica import NombreMetrica


class MetricaProduccionRepository(ABC):

    @abstractmethod
    def obtener_por_id(self, id_metrica_produccion: int) -> Optional[MetricaProduccion]:
        """Obtiene una métrica por su identidad. Retorna ``None`` si no existe."""
        raise NotImplementedError

    @abstractmethod
    def obtener_por_nombre_y_especie(
        self, nombre: NombreMetrica, id_especie: int
    ) -> Optional[MetricaProduccion]:
        """Busca una métrica por nombre normalizado dentro de una especie (unicidad por especie)."""
        raise NotImplementedError

    @abstractmethod
    def listar_por_especie(
        self, id_especie: int, *, solo_activas: bool = False
    ) -> list[MetricaProduccion]:
        """Retorna las métricas de una especie ordenadas por nombre."""
        raise NotImplementedError

    @abstractmethod
    def guardar(self, metrica: MetricaProduccion) -> MetricaProduccion:
        """Inserta una métrica nueva. Hace ``flush``. El ``commit`` lo emite el use case."""
        raise NotImplementedError

    @abstractmethod
    def actualizar(self, metrica: MetricaProduccion) -> MetricaProduccion:
        """Persiste cambios de una métrica existente. Hace ``flush``."""
        raise NotImplementedError

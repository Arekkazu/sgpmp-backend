"""Puerto de lectura de parámetros de producción por especie configurados en M09."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


@dataclass
class ParametroEspecie:
    """Parámetro de medición de una especie, con rango válido y unidad."""
    nombre: str
    tipo_medicion: str
    aplica_a_tipo_activo: str
    tipo_dato: str
    es_obligatorio: bool
    valor_min: Optional[Decimal] = field(default=None)
    valor_max: Optional[Decimal] = field(default=None)
    unidad_medida: Optional[str] = field(default=None)


@dataclass
class MetricaProductiva:
    """Métrica de producción del catálogo de M09 (leche, huevos, carne...).

    ``tipo_producto`` es el nombre de la métrica, que es lo que el usuario
    reconoce; ``tipo_medicion`` es la categoría (PESO, CONTEO...).
    """
    id_metrica_produccion: int
    tipo_producto: str
    unidad_medida: str
    aplica_a_tipo_activo: str
    tipo_medicion: str = ''
    tipo_dato: Optional[str] = None
    valor_min: Optional[Decimal] = None
    valor_max: Optional[Decimal] = None


@dataclass
class PatologiaEspecie:
    """Patología activa de la especie (RF-16), para el diagnóstico del evento sanitario."""
    id_patologia: int
    nombre: str


class ParametrosEspeciePort(ABC):
    """Consulta a M09 de densidad máxima, parámetros y métricas productivas por especie.
    """

    @abstractmethod
    def obtener_densidad_maxima(self, id_especie: int) -> Optional[Decimal]:
        """Retorna la densidad máxima configurada en M09 para la especie."""

    @abstractmethod
    def listar_por_especie(self, id_especie: int, tipo_activo: str) -> list[ParametroEspecie]:
        """Retorna los parámetros de producción activos para la especie y tipo de activo."""

    @abstractmethod
    def obtener_por_tipo_medicion(
        self, id_especie: int, tipo_medicion: str, tipo_activo: str
    ) -> Optional[ParametroEspecie]:
        """Retorna el parámetro de producción para la especie y tipo de medición dados, o None si no existe."""

    @abstractmethod
    def obtener_metrica_productiva(
        self, id_metrica_produccion: int, id_especie: int, tipo_activo: str
    ) -> Optional[MetricaProductiva]:
        """Retorna la métrica si está activa, es de la especie y aplica al tipo de activo; None si no."""

    @abstractmethod
    def listar_metricas_productivas(self, id_especie: int, tipo_activo: str) -> list[MetricaProductiva]:
        """Métricas activas de la especie que aplican al tipo de activo, ordenadas por nombre."""

    @abstractmethod
    def listar_patologias(self, id_especie: int) -> list[PatologiaEspecie]:
        """Patologías activas de la especie, ordenadas por nombre."""

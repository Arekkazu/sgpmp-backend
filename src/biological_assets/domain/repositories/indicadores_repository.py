"""Puerto de cálculo de indicadores zootécnicos (RF-51) y datos consolidados (RF-50)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional

from src.biological_assets.domain.entities.activo_biologico import DatosConsolidados, ResultadoIndicadores


class IndicadoresRepository(ABC):
    """Contrato de las consultas analíticas sobre un activo."""

    @abstractmethod
    def calcular_indicadores(
        self,
        id_activo: int,
        tipo_activo: str,
        fecha_inicio: Optional[date],
        fecha_fin: Optional[date],
        tipo_indicador: str,
    ) -> ResultadoIndicadores:
        """Calcula los indicadores del activo en el rango dado (RF-51).

        ``tipo_indicador`` filtra uno concreto; un indicador sin datos suficientes se
        devuelve con ``disponible=False`` y su causa.
        """

    @abstractmethod
    def obtener_datos_consolidados(
        self,
        id_activo: int,
        tipo_dato: str,
        fecha_inicio: Optional[date],
        fecha_fin: Optional[date],
        pagina: int,
        page_size: int,
    ) -> DatosConsolidados:
        """Arma la vista consolidada del activo para módulos analíticos (RF-50).

        ``tipo_dato`` elige qué secciones se llenan; los historiales se paginan.
        """

    @abstractmethod
    def contar_metricas_peso_en_rango(
        self,
        id_activo: int,
        fecha_inicio: Optional[date],
        fecha_fin: Optional[date],
    ) -> int:
        """Cuenta mediciones de peso (`eventos_crecimeinto.tipo_medicion='peso'`)
        del activo dentro del rango. Usado por RF-50 FA-03 (INC-M02-93-G93)
        para rechazar con 422 las consultas de valoración NIC-41 (M06) cuando
        el activo no registra peso en el periodo solicitado.
        """
        ...

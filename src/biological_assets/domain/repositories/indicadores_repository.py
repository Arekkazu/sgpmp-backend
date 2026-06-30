from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional

from src.biological_assets.domain.entities.activo_biologico import DatosConsolidados, ResultadoIndicadores


class IndicadoresRepository(ABC):

    @abstractmethod
    def calcular_indicadores(
        self,
        id_activo: int,
        tipo_activo: str,
        fecha_inicio: Optional[date],
        fecha_fin: Optional[date],
        tipo_indicador: str,
    ) -> ResultadoIndicadores: ...

    @abstractmethod
    def obtener_datos_consolidados(
        self,
        id_activo: int,
        tipo_dato: str,
        fecha_inicio: Optional[date],
        fecha_fin: Optional[date],
        pagina: int,
        page_size: int,
    ) -> DatosConsolidados: ...

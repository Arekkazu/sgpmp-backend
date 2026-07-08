from abc import ABC, abstractmethod
from typing import Optional

from src.telemetry.domain.entities.monitoreo import EstadoSensorActual, ResumenUnidadProductiva


class MonitoreoRepository(ABC):

    @abstractmethod
    def obtener_estados_sensores(
        self,
        id_infraestructura: Optional[int],
        pagina: int,
        por_pagina: int,
    ) -> tuple[list[EstadoSensorActual], int]:
        """Devuelve (sensores, total) del estado actual con contexto M09."""

    @abstractmethod
    def obtener_resumen_unidades(self) -> list[ResumenUnidadProductiva]:
        """Devuelve estado agregado por unidad productiva (para encabezado del dashboard)."""

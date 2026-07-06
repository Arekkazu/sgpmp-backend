from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.telemetry.domain.entities.telemetria import Telemetria


class TelemetriaRepository(ABC):

    @abstractmethod
    def guardar(self, entidad: Telemetria) -> Telemetria:
        """Persiste la telemetría y retorna la entidad con id asignado."""

    @abstractmethod
    def existe_duplicado(
        self,
        id_sensor: int,
        id_variable: int,
        timestamp_captura: datetime,
        origen: str,
        ventana_agregacion_min: Optional[int] = None,
    ) -> bool:
        """Verifica unicidad de la telemetría.

        Para EDGE_AGREGADO incluye ventana_agregacion_min en la clave compuesta.
        """

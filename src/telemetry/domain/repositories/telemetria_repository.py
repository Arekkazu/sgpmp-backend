from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
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

    @abstractmethod
    def obtener_serie_temporal(
        self,
        id_sensor: int,
        n: int,
        hasta_timestamp: datetime,
    ) -> list[Decimal]:
        """Retorna las últimas N lecturas válidas del sensor anteriores a hasta_timestamp."""

    @abstractmethod
    def actualizar_flags_aptitud(
        self,
        id_telemetria: int,
        apto_para_ia: bool,
        apto_para_nic41: bool,
    ) -> None:
        """Actualiza apto_para_ia y apto_para_nic41 en la fila de telemetría."""

# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de persistencia de lecturas de telemetría."""
from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Optional

from src.telemetry.domain.entities.telemetria import Telemetria


class TelemetriaRepository(ABC):
    """Puerto de persistencia y consulta de lecturas de telemetría."""

    @abstractmethod
    def guardar(self, entidad: Telemetria) -> Telemetria:
        """Persiste la telemetría y retorna la entidad con id asignado."""

    @abstractmethod
    def obtener_por_id(self, id_telemetria: int) -> Optional[Telemetria]:
        """Retorna la lectura y aptitud de su evaluación vigente RF-62, o None.

        Sin evaluación vigente, ambas aptitudes son False. Las columnas legadas
        de telemetrias no son fuente de aptitud.
        """

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

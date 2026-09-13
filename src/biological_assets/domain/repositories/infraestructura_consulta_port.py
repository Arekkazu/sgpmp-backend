from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from src.biological_assets.domain.entities.activo_biologico import SensorEnInfraestructura


@dataclass
class InfraestructuraConsulta:
    id_infraestructura: int
    nombre: str
    tipo: str
    es_activo: bool
    superficie: Optional[Decimal] = None
    id_finca: Optional[int] = None
    capacidad_maxima: Optional[int] = None
    id_especie: Optional[int] = None


class InfraestructuraConsultaPort(ABC):
    @abstractmethod
    def obtener_activa(self, id_infraestructura: int) -> Optional[InfraestructuraConsulta]:
        """Retorna la infraestructura si existe y está activa, None en caso contrario."""

    @abstractmethod
    def listar_activas(self, excluir_id: Optional[int] = None) -> list[InfraestructuraConsulta]:
        """Lista infraestructuras activas, excluyendo opcionalmente una por id."""

    @abstractmethod
    def calcular_ocupacion(self, id_infraestructura: int) -> int:
        """Retorna la cantidad total de individuos activos en la infraestructura."""

    @abstractmethod
    def listar_sensores_activos(self, id_infraestructura: int) -> list[SensorEnInfraestructura]:
        """Retorna los sensores con asociación de área activa en la infraestructura (enriquecimiento RF-22)."""

    @abstractmethod
    def es_tipo_compatible(self, tipo_infraestructura: str, id_especie: int) -> bool:
        """C2 (RF-48): compatibilidad entre el tipo de infraestructura y la especie del activo.

        Si no hay ninguna regla configurada para ``tipo_infraestructura``, es
        compatible por defecto (sin restricción todavía definida para ese tipo).
        Si hay al menos una regla, solo son compatibles las especies listadas.
        """

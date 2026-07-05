from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


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

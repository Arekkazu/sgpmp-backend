# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | #512 RF-16/RF-37: ciclos productivos de la especie con sus fases en orden |
"""Puerto de los ciclos productivos de una especie (RF-16, RF-37)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.ciclo_productivo import CicloProductivo


class CicloProductivoRepository(ABC):
    @abstractmethod
    def listar_por_especie(self, id_especie: int) -> list[CicloProductivo]:
        """Ciclos de la especie por nombre, cada uno con sus fases en orden."""

    @abstractmethod
    def obtener(self, id_ciclo_productivo: int) -> Optional[CicloProductivo]:
        """El ciclo con sus fases, o ``None``."""

    @abstractmethod
    def existe_nombre(self, id_especie: int, nombre: str, excluir: Optional[int] = None) -> bool:
        """Si la especie ya tiene un ciclo con ese nombre, sin distinguir mayúsculas."""

    @abstractmethod
    def guardar(self, ciclo: CicloProductivo) -> CicloProductivo:
        """Inserta o actualiza el ciclo y reescribe sus fases en orden. Hace ``flush``."""

    @abstractmethod
    def eliminar(self, id_ciclo_productivo: int) -> None:
        """Borra el ciclo, sus fases y las métricas habilitadas en él. Hace ``flush``."""

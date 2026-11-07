# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-25 RF-17: actualizar es_critica (RFC-016) |
"""Puerto (ABC) del catálogo de variables ambientales (CU03 RF-17)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.variable_ambiental import VariableAmbiental


class VariableAmbientalRepository(ABC):
    """Contrato de lectura del catálogo de variables ambientales."""

    @abstractmethod
    def obtener_por_id(self, id_variable_ambiental: int) -> Optional[VariableAmbiental]:
        """Obtiene la variable ambiental por id, o ``None`` si no existe."""

    @abstractmethod
    def listar_activas(self) -> list[VariableAmbiental]:
        """Variables ambientales activas del catálogo."""

    @abstractmethod
    def actualizar(self, variable: VariableAmbiental) -> VariableAmbiental:
        """RFC-016: persiste ``es_critica`` (el resto del catálogo no se edita)."""

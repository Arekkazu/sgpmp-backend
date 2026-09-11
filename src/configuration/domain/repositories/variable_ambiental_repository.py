"""Puerto (ABC) de lectura para el catálogo de variables ambientales (CU03 RF-17)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.variable_ambiental import VariableAmbiental


class VariableAmbientalRepository(ABC):
    @abstractmethod
    def obtener_por_id(self, id_variable_ambiental: int) -> Optional[VariableAmbiental]: ...

    @abstractmethod
    def listar_activas(self) -> list[VariableAmbiental]: ...

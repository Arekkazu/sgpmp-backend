# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-79: M06 provisional (recepción)        |
"""Puerto de la bandeja de entrada de provisiones de M06."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.financial_valuation.domain.entities.recepcion_provision import RecepcionProvision


class RecepcionProvisionRepository(ABC):
    @abstractmethod
    def registrar_si_nueva(self, recepcion: RecepcionProvision) -> bool:
        """Guarda la recepción; ``False`` si ese ``id_evento_provision`` ya se había recibido."""
        raise NotImplementedError

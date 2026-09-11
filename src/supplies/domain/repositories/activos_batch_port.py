"""Puerto para seleccionar los activos elegibles del batch ICA (RF-74).

El batch calcula el ICA de todos los activos en estado ACTIVO. Este puerto expone
la lista mínima que necesita el motor (id + fecha de inicio de ciclo, para priorizar).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class ActivoBatchRef:
    """Referencia mínima de un activo elegible para el batch."""

    id_activo_biologico: int
    fecha_inicio_ciclo: Optional[date]


class ActivosBatchPort(ABC):
    @abstractmethod
    def listar_activos_para_batch(self) -> list[ActivoBatchRef]:
        """Activos en estado ACTIVO candidatos al cálculo ICA."""
        raise NotImplementedError

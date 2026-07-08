from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class ActivoBiologicoInfo:
    id_activo_biologico: int
    modelo_manejo: str  # INDIVIDUAL | POBLACIONAL


class ActivoBiologicoDependencyPort(ABC):
    """Puerto hacia M02 para resolver qué activo biológico estaba asociado
    a una infraestructura en un momento dado.
    """

    @abstractmethod
    def obtener_activos_en_momento(
        self, id_infraestructura: int, timestamp: datetime
    ) -> List[ActivoBiologicoInfo]:
        """Retorna los activos biológicos asociados a la infraestructura en el timestamp.
        Lista vacía → SIN_VINCULAR. Más de uno → AMBIGUA. Exactamente uno → VINCULADA.
        """
        ...

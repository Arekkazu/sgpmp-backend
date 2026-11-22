# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-44 RF-61: contrato de contexto y candidatos historicos |
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class ActivoBiologicoInfo:
    id_activo_biologico: int
    modelo_manejo: str  # INDIVIDUAL | POBLACIONAL
    contexto: Optional[dict] = None


class ActivoBiologicoDependencyPort(ABC):
    """Puerto hacia M02 para resolver qué activo biológico estaba asociado
    a una infraestructura en un momento dado.
    """

    @abstractmethod
    def obtener_activos_en_momento(
        self, id_infraestructura: int, timestamp: datetime
    ) -> List[ActivoBiologicoInfo]:
        """Retorna los activos biológicos asociados a la infraestructura en el timestamp.
        Lista vacía → SIN_VINCULAR. Más de uno → AMBIGUA. Exactamente uno → CONFIRMADA.
        """
        ...

    def obtener_contexto(self, id_activo_biologico: int, timestamp: datetime) -> dict:
        """Snapshot aplicable a la captura; no reemplazarlo por valores actuales."""
        raise NotImplementedError

    def historial_inconsistente(self, id_infraestructura: int, timestamp: datetime) -> bool:
        raise NotImplementedError

    def bloquear_activos(self, identificadores: list[int]) -> None:
        """Estabiliza la ocupacion antes de confirmar el snapshot de vinculacion."""
        raise NotImplementedError

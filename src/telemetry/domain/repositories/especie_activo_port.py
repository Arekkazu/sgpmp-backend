from abc import ABC, abstractmethod
from typing import Optional


class EspecieActivoPort(ABC):
    """Puerto hacia M02 para resolver la especie de un activo biológico ya vinculado."""

    @abstractmethod
    def obtener_id_especie(self, id_activo_biologico: int) -> Optional[int]:
        """Retorna el id_especie del activo biológico, o None si no existe."""

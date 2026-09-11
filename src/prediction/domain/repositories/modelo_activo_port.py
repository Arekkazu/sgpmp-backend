from __future__ import annotations

from abc import ABC, abstractmethod


class ModeloActivoPort(ABC):
    @abstractmethod
    def tiene_modelos_activos(self, id_patologia: int) -> bool:
        """Retorna True si la patología está en uso como clase objetivo en modelos EN_VALIDACION o ACTIVO."""
        ...

from __future__ import annotations

from abc import ABC, abstractmethod


class ActivoBiologicoPort(ABC):
    @abstractmethod
    def activo_existe_y_accesible(self, id_activo: int, id_usuario: int, id_rol: int) -> bool: ...

# | Fecha      | Nombre   | Que se hizo                                             |
# |------------|----------|---------------------------------------------------------|
# | 2026-10-30 | Arekkazu | RF-66: especie del activo para el resultado del motor IA |
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class ActivoBiologicoPort(ABC):
    @abstractmethod
    def activo_existe_y_accesible(self, id_activo: int, id_usuario: int, id_rol: int) -> bool: ...

    @abstractmethod
    def obtener_especie(self, id_activo: int) -> Optional[int]:
        """id_especie del activo, o None si no existe (RF-66: lo usa el motor IA)."""
        ...

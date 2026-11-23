# | Fecha      | Nombre   | Que se hizo                                             |
# |------------|----------|---------------------------------------------------------|
# | 2026-10-30 | Arekkazu | RF-66: especie del activo para el resultado del motor IA |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de acceso a activos biológicos desde el motor."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class ActivoBiologicoPort(ABC):
    """Puerto para verificar el acceso a un activo."""
    @abstractmethod
    def activo_existe_y_accesible(self, id_activo: int, id_usuario: int, id_rol: int) -> bool:
        """Indica si el activo existe y el usuario lo puede ver."""
        ...

    @abstractmethod
    def obtener_especie(self, id_activo: int) -> Optional[int]:
        """id_especie del activo, o None si no existe (RF-66: lo usa el motor IA)."""
        ...

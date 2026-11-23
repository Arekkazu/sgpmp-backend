# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-66: cámaras de visión de un área (para ver sus capturas)      |
# | 2026-11-02 | Arekkazu | RF-66 POBLACIONAL: inventario del área y conteos de la cámara      |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de cámaras de un área."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class CamarasAreaPort(ABC):
    """Puerto para listar las cámaras de un área."""

    @abstractmethod
    def camaras(self, id_area: int) -> list[int]:
        """Cámaras del área que el usuario puede ver (RLS de M09): vacía si el área no es suya."""

    @abstractmethod
    def cantidad_registrada(self, id_area: int) -> Optional[int]:
        """Suma de ``cantidad_actual`` de los lotes POBLACIONAL vigentes del área (M02); None si no hay."""

    @abstractmethod
    def conteos_recientes(self, id_area: int, limite: int) -> list[int]:
        """Individuos que vio la cámara en las últimas ventanas aptas (RF-62), del más nuevo al más viejo."""

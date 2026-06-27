"""Puerto de persistencia del catálogo global de patologías (capa de dominio).

M09 CU02 gestiona nombre, descripcion y es_activo.
Los campos de M04 se preservan sin modificar al actualizar.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.patologia import Patologia
from src.configuration.domain.value_objects.nombre_patologia import NombrePatologia


class PatologiaRepository(ABC):

    @abstractmethod
    def obtener_por_id(self, id_patologia: int) -> Optional[Patologia]:
        """Obtiene una patología por su identidad. Retorna ``None`` si no existe."""
        raise NotImplementedError

    @abstractmethod
    def obtener_por_nombre(self, nombre: NombrePatologia) -> Optional[Patologia]:
        """Busca una patología por nombre normalizado (unicidad global, case-insensitive)."""
        raise NotImplementedError

    @abstractmethod
    def guardar(self, patologia: Patologia, id_usuario_creador: Optional[int] = None) -> Patologia:
        """Inserta una patología nueva. Hace ``flush``."""
        raise NotImplementedError

    @abstractmethod
    def actualizar(self, patologia: Patologia) -> Patologia:
        """Persiste cambios de nombre, descripcion y es_activo. Hace ``flush``."""
        raise NotImplementedError

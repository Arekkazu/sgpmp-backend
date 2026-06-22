"""Puerto de persistencia del agregado ``Plantilla`` (capa de dominio).

Define el contrato que la capa de aplicación usa para leer y guardar plantillas
de configuración (RF-30, RF-31).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.plantilla import Plantilla


class PlantillaRepository(ABC):

    @abstractmethod
    def obtener_por_id(self, id_plantilla: int) -> Optional[Plantilla]:
        """Obtiene una plantilla por su PK. Retorna ``None`` si no existe."""
        raise NotImplementedError

    @abstractmethod
    def obtener_version_maxima(self, template_name: str) -> Optional[int]:
        """Retorna la versión más alta para un nombre dado. ``None`` si no existe."""
        raise NotImplementedError

    @abstractmethod
    def listar_todas(self) -> list[Plantilla]:
        """Retorna todas las plantillas ordenadas por nombre y versión desc."""
        raise NotImplementedError

    @abstractmethod
    def guardar(self, plantilla: Plantilla) -> Plantilla:
        """Inserta una plantilla nueva. Hace ``flush``. El ``commit`` lo emite el use case."""
        raise NotImplementedError

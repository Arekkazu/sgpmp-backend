"""Puerto de persistencia del registro de aplicaciones de plantillas (capa de dominio).

Permite insertar eventos de aplicación (RF-32) y consultar el historial.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.configuration.domain.entities.aplicacion_plantilla import AplicacionPlantilla


class AplicacionPlantillaRepository(ABC):

    @abstractmethod
    def guardar(self, aplicacion: AplicacionPlantilla) -> AplicacionPlantilla:
        """Inserta el registro de aplicación. Hace ``flush``."""
        raise NotImplementedError

    @abstractmethod
    def listar_todas(self) -> list[AplicacionPlantilla]:
        """Retorna todas las aplicaciones ordenadas por fecha desc."""
        raise NotImplementedError

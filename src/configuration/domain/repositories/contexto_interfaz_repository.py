"""Puerto de lectura del read-model ``ContextoInterfaz`` (RF-25)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.configuration.domain.entities.contexto_interfaz import ContextoInterfaz


class ContextoInterfazRepository(ABC):

    @abstractmethod
    def obtener_por_usuario(self, id_usuario: int, id_rol: int) -> ContextoInterfaz:
        raise NotImplementedError

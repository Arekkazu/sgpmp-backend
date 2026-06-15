"""Puerto de persistencia del agregado ``CicloBiologico`` (capa de dominio).

Define el contrato que la capa de aplicación usa para leer y guardar etapas
del ciclo productivo por especie (RF-16).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.ciclo_biologico import CicloBiologico
from src.configuration.domain.value_objects.nombre_etapa import NombreEtapa


class CicloBiologicoRepository(ABC):

    @abstractmethod
    def obtener_por_id(self, id_ciclo_biologico: int) -> Optional[CicloBiologico]:
        """Obtiene una etapa por su identidad. Retorna ``None`` si no existe."""
        raise NotImplementedError

    @abstractmethod
    def obtener_por_nombre_y_especie(
        self, nombre: NombreEtapa, id_especie: int
    ) -> Optional[CicloBiologico]:
        """Busca una etapa por nombre normalizado dentro de una especie (unicidad por especie)."""
        raise NotImplementedError

    @abstractmethod
    def listar_por_especie(
        self, id_especie: int, *, solo_activas: bool = False
    ) -> list[CicloBiologico]:
        """Retorna las etapas de una especie ordenadas por nombre."""
        raise NotImplementedError

    @abstractmethod
    def guardar(self, ciclo: CicloBiologico) -> CicloBiologico:
        """Inserta una etapa nueva. Hace ``flush``. El ``commit`` lo emite el use case."""
        raise NotImplementedError

    @abstractmethod
    def actualizar(self, ciclo: CicloBiologico) -> CicloBiologico:
        """Persiste cambios de una etapa existente. Hace ``flush``."""
        raise NotImplementedError

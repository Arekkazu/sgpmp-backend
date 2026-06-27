"""Puerto (ABC) de persistencia para el agregado UmbralAmbiental (CU03 RF-17)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.umbral_ambiental import UmbralAmbiental


class UmbralAmbientalRepository(ABC):
    @abstractmethod
    def obtener_por_id(self, id_umbral_ambiental: int) -> Optional[UmbralAmbiental]: ...

    @abstractmethod
    def obtener_por_especie_y_variable(
        self, id_especie: int, id_variable_ambiental: int
    ) -> Optional[UmbralAmbiental]: ...

    @abstractmethod
    def listar_por_especie(
        self, id_especie: int, *, solo_activas: bool = False
    ) -> list[UmbralAmbiental]: ...

    @abstractmethod
    def guardar(self, umbral: UmbralAmbiental) -> UmbralAmbiental: ...

    @abstractmethod
    def actualizar(self, umbral: UmbralAmbiental) -> UmbralAmbiental: ...

    @abstractmethod
    def desactivar_todos_por_especie(self, id_especie: int) -> None:
        """Marca como inactivos todos los umbrales activos de una especie. Hace ``flush``."""
        raise NotImplementedError

    @abstractmethod
    def guardar_desde_snapshot(self, datos: dict, id_especie: int, id_usuario: int) -> None:
        """Inserta un umbral + niveles a partir de un dict del params_snapshot. Hace ``flush``."""
        raise NotImplementedError

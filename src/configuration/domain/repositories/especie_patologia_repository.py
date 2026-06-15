"""Puerto de persistencia del pivot especie ↔ patología (capa de dominio).

Gestiona las asociaciones entre patologías globales y especies específicas
a través de la tabla `modulo9.especies_patologias`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.especie_patologia import EspeciePatologia


class EspeciePatologiaRepository(ABC):

    @abstractmethod
    def obtener_por_especie_y_patologia(
        self, id_especie: int, id_patologia: int
    ) -> Optional[EspeciePatologia]:
        """Busca la asociación entre una especie y una patología. Retorna ``None`` si no existe."""
        raise NotImplementedError

    @abstractmethod
    def listar_por_especie(
        self, id_especie: int, *, solo_activas: bool = False
    ) -> list[EspeciePatologia]:
        """Retorna las patologías asociadas a una especie, con datos de la patología global."""
        raise NotImplementedError

    @abstractmethod
    def asociar(self, id_especie: int, id_patologia: int) -> EspeciePatologia:
        """Crea la asociación especie ↔ patología. Hace ``flush``."""
        raise NotImplementedError

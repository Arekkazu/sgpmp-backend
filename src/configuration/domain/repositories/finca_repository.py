"""Puerto de persistencia del agregado ``Finca`` (RF-19)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.finca import Finca
from src.configuration.domain.value_objects.nombre_finca import NombreFinca


class FincaRepository(ABC):

    @abstractmethod
    def obtener_por_id(self, id_finca: int) -> Optional[Finca]:
        raise NotImplementedError

    @abstractmethod
    def obtener_por_nombre(self, nombre: NombreFinca) -> Optional[Finca]:
        """Busca case-insensitive para verificar unicidad global."""
        raise NotImplementedError

    @abstractmethod
    def guardar(self, finca: Finca) -> Finca:
        raise NotImplementedError

    @abstractmethod
    def actualizar(self, finca: Finca) -> Finca:
        raise NotImplementedError

    @abstractmethod
    def listar(self, *, id_usuario_filtro: Optional[int] = None, solo_activas: bool = False) -> list[Finca]:
        """Lista fincas. Si id_usuario_filtro es provisto, filtra por productor."""
        raise NotImplementedError

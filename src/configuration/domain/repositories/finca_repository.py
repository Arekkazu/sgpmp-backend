"""Puerto de persistencia del agregado ``Finca`` (RF-19)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.finca import Finca
from src.configuration.domain.value_objects.nombre_finca import NombreFinca


class FincaRepository(ABC):

    @abstractmethod
    def obtener_por_id(self, id_finca: int, *, bloquear: bool = False) -> Optional[Finca]:
        """``bloquear=True`` toma la fila con ``SELECT ... FOR UPDATE`` (#498)."""
        raise NotImplementedError

    @abstractmethod
    def obtener_por_nombre(self, nombre: NombreFinca) -> Optional[Finca]:
        """Busca case-insensitive para verificar unicidad global."""
        raise NotImplementedError

    @abstractmethod
    def guardar(self, finca: Finca, id_creador: Optional[int] = None) -> Finca:
        """``id_creador`` también queda con acceso: ningún rol es global (F4)."""
        raise NotImplementedError

    @abstractmethod
    def actualizar(self, finca: Finca) -> Finca:
        raise NotImplementedError

    @abstractmethod
    def listar(self, *, ids_fincas: Optional[list[int]] = None, solo_activas: bool = False) -> list[Finca]:
        """Lista fincas; ``ids_fincas`` limita el resultado (``None`` = todas)."""
        raise NotImplementedError

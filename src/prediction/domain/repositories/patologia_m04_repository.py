from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.prediction.domain.entities.patologia_m04 import PatologiaM04


class PatologiaM04Repository(ABC):
    @abstractmethod
    def obtener_por_id(self, id_patologia: int) -> Optional[PatologiaM04]: ...

    @abstractmethod
    def obtener_por_nombre(self, nombre: str) -> Optional[PatologiaM04]:
        """Búsqueda case-insensitive en el catálogo global."""
        ...

    @abstractmethod
    def obtener_por_combinacion_variables(
        self, ids_variables: list[int], especie_aplicable: str, excluir_id: Optional[int] = None
    ) -> Optional[PatologiaM04]:
        """Devuelve la patología con exactamente el mismo conjunto de variables para la misma especie, si existe."""
        ...

    @abstractmethod
    def guardar(self, entidad: PatologiaM04) -> PatologiaM04: ...

    @abstractmethod
    def actualizar(self, entidad: PatologiaM04) -> PatologiaM04: ...

    @abstractmethod
    def listar(
        self,
        especie_aplicable: Optional[str] = None,
        solo_activas: Optional[bool] = None,
        solo_base: Optional[bool] = None,
    ) -> list[PatologiaM04]: ...

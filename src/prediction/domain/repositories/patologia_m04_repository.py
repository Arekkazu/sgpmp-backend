# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-25 | Arekkazu | INC-M04-139-G001/138-G001 RF-64: versión del catálogo y búsqueda por nombre |
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.prediction.domain.entities.patologia_m04 import PatologiaM04


class PatologiaM04Repository(ABC):
    @abstractmethod
    def obtener_por_id(self, id_patologia: int, *, bloquear: bool = False) -> Optional[PatologiaM04]:
        """``bloquear=True`` toma la fila con ``SELECT ... FOR UPDATE`` (#498)."""

    @abstractmethod
    def obtener_por_nombre(self, nombre: str) -> Optional[PatologiaM04]:
        """Búsqueda en el catálogo global sin distinguir mayúsculas ni espacios repetidos."""
        ...

    @abstractmethod
    def obtener_por_combinacion_variables(
        self, ids_variables: list[int], especie_aplicable: str, excluir_id: Optional[int] = None
    ) -> Optional[PatologiaM04]:
        """Devuelve la patología con exactamente el mismo conjunto de variables para la misma especie, si existe."""
        ...

    @abstractmethod
    def siguiente_version_catalogo(self) -> int:
        """Versión que toma el próximo cambio del catálogo; serializa los cambios hasta el commit."""
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
        nombre: Optional[str] = None,
    ) -> list[PatologiaM04]: ...

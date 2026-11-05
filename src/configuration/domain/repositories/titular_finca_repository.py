# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | RF-19 v1.1: puerto del titular tributario de la finca |
"""Puerto del titular tributario de la finca (RF-19 v1.1)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.value_objects.titular_tributario import TitularTributario


class TitularFincaRepository(ABC):
    @abstractmethod
    def obtener(self, id_finca: int) -> Optional[dict]: ...

    @abstractmethod
    def otro_con_mismo_numero(self, numero_id_tributaria: str, id_finca: int) -> Optional[dict]:
        """Otra finca del mismo titular (para exigir la misma razón social y DV)."""

    @abstractmethod
    def guardar(self, id_finca: int, titular: Optional[TitularTributario]) -> None: ...

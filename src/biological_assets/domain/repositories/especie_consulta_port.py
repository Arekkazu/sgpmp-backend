from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class EspecieConsulta:
    id_especie: int
    nombre: str
    es_activo: bool


class EspecieConsultaPort(ABC):
    @abstractmethod
    def obtener_activa(self, id_especie: int) -> Optional[EspecieConsulta]:
        """Retorna la especie si existe y está activa, None en caso contrario."""

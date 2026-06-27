from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class InfraestructuraConsulta:
    id_infraestructura: int
    nombre: str
    tipo: str
    es_activo: bool


class InfraestructuraConsultaPort(ABC):
    @abstractmethod
    def obtener_activa(self, id_infraestructura: int) -> Optional[InfraestructuraConsulta]:
        """Retorna la infraestructura si existe y está activa, None en caso contrario."""

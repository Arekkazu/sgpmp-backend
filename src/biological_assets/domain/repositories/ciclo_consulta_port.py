from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class FaseCiclo:
    id_ciclos_productivo_biologico: int
    id_ciclo_biologico: int
    nombre_fase: str
    duracion_dias: int


@dataclass
class CicloProductivoConsulta:
    id_ciclo_productivo: int
    nombre: str
    fases: list[FaseCiclo]


class CicloConsultaPort(ABC):
    @abstractmethod
    def obtener_ciclo_con_fases(self, id_ciclo_productivo: int) -> Optional[CicloProductivoConsulta]:
        """Retorna el ciclo productivo con su secuencia de fases biológicas ordenadas, o None si no existe."""

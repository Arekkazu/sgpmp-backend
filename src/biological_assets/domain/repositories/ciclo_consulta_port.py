"""Puerto de lectura de ciclos productivos configurados en M09 (RF-37, RF-43)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class FaseCiclo:
    """Una fase de la secuencia de un ciclo productivo, con su duración esperada."""
    id_ciclos_productivo_biologico: int
    id_ciclo_biologico: int
    nombre_fase: str
    duracion_dias: int


@dataclass
class CicloProductivoConsulta:
    """Ciclo productivo de M09 con sus fases en orden."""
    id_ciclo_productivo: int
    nombre: str
    fases: list[FaseCiclo]
    # Especie del ciclo, vía su ciclo biológico de referencia. None si el
    # ciclo no tiene uno (no se puede validar la compatibilidad).
    id_especie: Optional[int] = None


class CicloConsultaPort(ABC):
    """Consulta a M09 de ciclos, fases y métricas habilitadas por ciclo."""

    @abstractmethod
    def obtener_ciclo_con_fases(self, id_ciclo_productivo: int) -> Optional[CicloProductivoConsulta]:
        """Retorna el ciclo productivo con su secuencia de fases biológicas ordenadas, o None si no existe."""

    @abstractmethod
    def listar_por_especie(self, id_especie: int) -> list[CicloProductivoConsulta]:
        """Ciclos productivos de la especie, cada uno con sus fases ordenadas."""

    @abstractmethod
    def metrica_habilitada_en_ciclo(self, id_ciclo_productivo: int, id_metrica_produccion: int) -> bool:
        """Retorna True si la métrica está registrada en metricas_ciclo_productivo para ese ciclo."""

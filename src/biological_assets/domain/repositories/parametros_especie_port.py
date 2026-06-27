from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ParametroEspecie:
    nombre: str
    tipo_medicion: str
    aplica_a_tipo_activo: str


class ParametrosEspeciePort(ABC):
    @abstractmethod
    def listar_por_especie(self, id_especie: int, tipo_activo: str) -> list[ParametroEspecie]:
        """Retorna los parámetros de producción activos para la especie y tipo de activo."""

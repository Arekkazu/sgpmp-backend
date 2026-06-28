from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


@dataclass
class ParametroEspecie:
    nombre: str
    tipo_medicion: str
    aplica_a_tipo_activo: str
    valor_min: Optional[Decimal] = field(default=None)
    valor_max: Optional[Decimal] = field(default=None)


class ParametrosEspeciePort(ABC):
    @abstractmethod
    def listar_por_especie(self, id_especie: int, tipo_activo: str) -> list[ParametroEspecie]:
        """Retorna los parámetros de producción activos para la especie y tipo de activo."""

    @abstractmethod
    def obtener_por_tipo_medicion(
        self, id_especie: int, tipo_medicion: str, tipo_activo: str
    ) -> Optional[ParametroEspecie]:
        """Retorna el parámetro de producción para la especie y tipo de medición dados, o None si no existe."""

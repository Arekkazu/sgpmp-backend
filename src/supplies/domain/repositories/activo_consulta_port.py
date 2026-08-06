"""Puerto de consulta del activo biológico (RF-33 / RF-36) para el módulo de suministros.

El dominio de suministros solo necesita leer ciertos atributos del activo para
validar el registro: su estado, su tipo (INDIVIDUAL/POBLACIONAL), la cantidad
actual del lote (para el cálculo por individuo) y la fecha de inicio de ciclo.
La implementación concreta vive en ``infrastructure/adapters`` y consulta
``modulo2``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Optional

ESTADO_ACTIVO = 1
ESTADO_EN_TRATAMIENTO = 3


@dataclass
class ActivoConsulta:
    """Vista de solo lectura del activo biológico para el módulo de suministros."""

    id_activo_biologico: int
    tipo: str
    id_estado: int
    nombre_estado: Optional[str]
    cantidad_actual: Optional[int]
    fecha_inicio_ciclo: Optional[date]

    @property
    def es_poblacional(self) -> bool:
        return (self.tipo or "").upper() == "POBLACIONAL"

    @property
    def esta_activo(self) -> bool:
        return self.id_estado == ESTADO_ACTIVO

    @property
    def esta_en_tratamiento(self) -> bool:
        return self.id_estado == ESTADO_EN_TRATAMIENTO


class ActivoConsultaPort(ABC):
    """Contrato de consulta del activo biológico."""

    @abstractmethod
    def obtener(self, id_activo: int) -> Optional[ActivoConsulta]:
        """Devuelve la vista del activo o ``None`` si no existe."""
        raise NotImplementedError

    @abstractmethod
    def listar_en_tratamiento(self) -> list[int]:
        """Devuelve los ``id_activo_biologico`` actualmente en estado EN_TRATAMIENTO.

        Usado por el scheduler de reversión de retiro (RF-76 pasos 11-13).
        """
        raise NotImplementedError

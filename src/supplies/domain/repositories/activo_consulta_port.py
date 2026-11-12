# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | #512 RF-75/76: los mensajes nombran el activo por su identificador, no por su id |
# | 2026-11-12 | LuisfNarvaez01 | INC-M05-358-G43 RF-81: existe() distingue un activo ajeno (403) de uno inexistente (404) |
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
    identificador: Optional[str] = None

    @property
    def nombre_visible(self) -> str:
        """Cómo se nombra el activo en un mensaje: su identificador, nunca el id interno."""
        return self.identificador or "seleccionado"

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

    def existe(self, id_activo: int) -> bool:
        """``True`` si el activo existe aunque el usuario no lo vea (403 en vez de 404, RF-81 E2).

        No devuelve ningún dato del activo. Por defecto ``False`` (adaptadores sin la consulta).
        """
        return False

    @abstractmethod
    def listar_en_tratamiento(self) -> list[int]:
        """Devuelve los ``id_activo_biologico`` actualmente en estado EN_TRATAMIENTO.

        Usado por el scheduler de reversión de retiro (RF-76 pasos 11-13).
        """
        raise NotImplementedError

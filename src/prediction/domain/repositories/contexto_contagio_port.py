# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-68: contexto del lote para el disparo automático tras RF-66   |
"""Lo que RF-68 necesita del lote y de su área cuando corre sin un cliente que lo envíe."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class AmbienteArea:
    temperatura: Optional[Decimal]
    humedad_relativa: Optional[Decimal]
    #: La más antigua de las dos lecturas: es la que decide la sincronía con la inferencia.
    fecha_captura: datetime


@dataclass(frozen=True)
class ContextoContagio:
    #: Animales/m² del área. Negativa pide a RF-68 el promedio registrado del lote (E2).
    densidad_poblacional: Optional[Decimal]
    porcentaje_sensores_activos: Decimal
    ambiente: Optional[AmbienteArea]


class ContextoContagioPort(ABC):
    @abstractmethod
    def obtener(self, id_activo: int, instante: datetime) -> Optional[ContextoContagio]:
        """None si el activo no existe. ``ambiente``: últimas lecturas del área hasta ``instante``."""

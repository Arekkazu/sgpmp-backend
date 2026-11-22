# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-66 POBLACIONAL: lo que el puntaje de anomalía lee de M02/M03/M09 |
"""Puerto de RF-66 POBLACIONAL: observación de visión evaluada (M03), lotes del área (M02) y
línea base del área y especie (M09, RF-24)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class ObservacionPoblacional:
    id_observacion: int
    id_area: int
    vector: dict
    apto_para_ia: bool
    confianza_baja: bool
    fecha_inicio: Optional[datetime]
    fecha_fin: datetime


@dataclass(frozen=True)
class LotePoblacional:
    id_activo: int
    id_especie: int
    #: ``tipo_modelo_asignado`` del área (RFC-009): el que elige el modelo.
    tipo_modelo: str


class ObservacionPoblacionalPort(ABC):

    @abstractmethod
    def obtener(self, id_observacion: int) -> Optional[ObservacionPoblacional]: ...

    @abstractmethod
    def lotes(self, id_area: int) -> list[LotePoblacional]:
        """Lotes POBLACIONAL vigentes del área, solo si el área tiene un modelo POBLACIONAL."""

    @abstractmethod
    def linea_base(self, id_area: int, id_especie: int) -> Optional[dict]:
        """``{componente: mediana}`` vigente de RF-24, o None si el par no está calibrado."""

    @abstractmethod
    def ya_evaluado(self, id_activo: int, tipo_modelo: str, fecha_fin: datetime) -> bool:
        """Ya hay un resultado de esa ventana: el worker reintenta y no debe duplicarlo."""

"""Puerto de dependencia hacia M02 (activos biológicos) para RF-22.

Issue #290 (SEG-M09-01): al reasignar un sensor de área, las asociaciones
sensor→activo de tipo AMBIENTAL (el sensor mide el activo por compartir
área) y POBLACIONAL (mide un lote ubicado en un área) dejan de sostener la
premisa espacial que las justificó (RF-49 V6). DIRECTA no depende del área
del sensor — se vincula al individuo, no al lugar — y no se toca.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AsociacionActivoSuperada:
    """Asociación sensor→activo que una reasignación de área dejó SUPERADA.

    Se devuelve al cliente para que sepa qué activos dejó de monitorear el
    sensor y pueda re-asociarlos vía RF-49 si lo desea (sugerencia de Análisis
    en PR #304: no dejar el sensor "sin monitoreo" en silencio).
    """

    id_asociacion_activo_sensor: int
    id_activo_biologico: Optional[int]
    tipo: str


class AsociacionSensorActivoDependencyPort(ABC):

    @abstractmethod
    def superar_ambientales_y_poblacionales(
        self,
        id_sensor: int,
        id_usuario: int,
        motivo: str,
    ) -> list[AsociacionActivoSuperada]:
        """Marca SUPERADA toda asociación ACTIVA ambiental/poblacional de
        `id_sensor` y registra la auditoría correspondiente en modulo2.

        Devuelve las asociaciones cerradas (lista vacía si el sensor no tenía
        ninguna vigente de esos tipos).
        """

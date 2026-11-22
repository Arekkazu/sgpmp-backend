# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-169-G77 RF-57 Fase 3: contexto del activo biológico de la alerta |
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class ContextoActivoAlerta:
    """Resultado de la Fase 3 de RF-57: con ``id_activo_biologico`` el contexto está completo; sin él,
    ``motivo`` dice por qué (E6 / CA-7)."""
    id_activo_biologico: Optional[int]
    contexto: Optional[dict]
    fuente: Optional[str]          # VINCULACION_RF61 | ASOCIACION_SENSOR | ASOCIACION_AMBIENTAL | UNIDAD_PRODUCTIVA
    motivo: Optional[str] = None   # SIN_ACTIVO_ASOCIADO | VARIOS_ACTIVOS_CANDIDATOS


class ContextoActivoAlertaPort(ABC):
    @abstractmethod
    def resolver(self, id_sensor: int, id_infraestructura: Optional[int], momento: datetime,
                 id_telemetria: Optional[int] = None) -> ContextoActivoAlerta:
        """Activo biológico del sensor en ``momento`` y su contexto (lote/animal, especie, unidad, ubicación)."""

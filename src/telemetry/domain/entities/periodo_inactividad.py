from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, List, Optional


@dataclass
class PeriodoInactividad:
    id_periodo_inactividad: Optional[int]
    id_dispositivo_iot: int
    sensores_afectados: List[int]
    fecha_inicio: Optional[datetime]
    fecha_fin: Optional[datetime]
    duracion_min: Optional[int]
    estado_durante_periodo: str
    causa_primaria: str
    caso_diagnosticado: Any
    buffer_activo_durante: bool
    id_alerta: Optional[int]

    def cerrar(self, fecha_fin: datetime) -> None:
        self.fecha_fin = fecha_fin
        if self.fecha_inicio is not None:
            delta = fecha_fin - self.fecha_inicio
            self.duracion_min = int(delta.total_seconds() / 60)

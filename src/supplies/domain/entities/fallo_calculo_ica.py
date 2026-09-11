"""Entidad de dominio :class:`FalloCalculoICA` (RF-74 / E5).

Registra un fallo técnico persistente del cálculo ICA de un activo tras agotar los
reintentos (estado de negocio ``CA_FALLO_PERSISTENTE``). Se resuelve por reintento
manual (panel admin) o automático.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.supplies.domain.value_objects.eficiencia_enums import PeriodoEvaluacion


@dataclass(eq=False)
class FalloCalculoICA:
    """Fallo técnico persistente del cálculo ICA de un activo."""

    id_activo_biologico: int
    causa_fallo: str
    intentos: int
    periodo_evaluacion: Optional[PeriodoEvaluacion] = None
    timestamp_ultimo_intento: Optional[datetime] = None
    id_ejecucion_batch: Optional[int] = None
    resuelto: bool = False
    fecha_resolucion: Optional[datetime] = None
    tipo_resolucion: Optional[str] = None  # MANUAL | AUTOMATICO
    id_fallo: Optional[int] = None

    def resolver(self, *, tipo_resolucion: str, cuando: datetime) -> None:
        self.resuelto = True
        self.tipo_resolucion = tipo_resolucion
        self.fecha_resolucion = cuando

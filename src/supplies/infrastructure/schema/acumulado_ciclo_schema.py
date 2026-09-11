"""Schema de respuesta para la consulta del acumulado de inversión (RF-78)."""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class AcumuladoCicloResponse(BaseModel):
    """Acumulado de inversión de una instancia de ciclo productivo."""

    id_activo_biologico: int
    id_ciclo_productivo: int
    id_gestion_fases: int
    acumulado_total_ciclo: Decimal
    acumulado_por_categoria: dict[str, Decimal]
    version_acumulado: int
    estado: str
    fecha_ultima_actualizacion: Optional[datetime.datetime]

    model_config = {"from_attributes": True}

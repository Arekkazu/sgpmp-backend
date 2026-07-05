from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from src.shared.base_dto import BaseDTO


class ConsultarBitacoraDTO(BaseDTO):
    rf_origen: Optional[str] = None
    tipo_evento: Optional[str] = None
    id_activo_biologico: Optional[int] = None
    clasificacion_biologica: Optional[str] = None
    resultado: Optional[str] = None
    severidad_log: Optional[str] = None
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None
    pagina: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

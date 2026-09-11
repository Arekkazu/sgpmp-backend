from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.shared.base_dto import BaseDTO


class CambiarFaseDTO(BaseDTO):
    id_ciclo_productiva: int
    motivo_cambio: Optional[str] = None
    fecha_inicio: Optional[datetime] = None

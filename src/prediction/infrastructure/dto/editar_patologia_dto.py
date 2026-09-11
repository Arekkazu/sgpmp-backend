from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.shared.base_dto import BaseDTO


class EditarPatologiaDTO(BaseDTO):
    nombre_patologia: str
    descripcion_clinica: str
    variables_sensoricas_asociadas: list[int]
    fecha_actualizacion: Optional[datetime] = None

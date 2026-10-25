# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
from __future__ import annotations

from typing import Optional

from src.shared.base_dto import BaseDTO
from src.shared.fechas import FechaHoraUtc


class EditarPatologiaDTO(BaseDTO):
    nombre_patologia: str
    descripcion_clinica: str
    variables_sensoricas_asociadas: list[int]
    fecha_actualizacion: Optional[FechaHoraUtc] = None

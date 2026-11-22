# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
# | 2026-10-25 | Arekkazu | INC-M04-140-G003 RF-64: nombre con espacios internos normalizados |
from __future__ import annotations

from typing import Optional

from pydantic import field_validator

from src.prediction.infrastructure.dto.registrar_patologia_dto import normalizar_nombre_patologia
from src.shared.base_dto import BaseDTO
from src.shared.fechas import FechaHoraUtc


class EditarPatologiaDTO(BaseDTO):
    nombre_patologia: str
    descripcion_clinica: str
    variables_sensoricas_asociadas: list[int]
    fecha_actualizacion: Optional[FechaHoraUtc] = None

    _nombre = field_validator("nombre_patologia")(normalizar_nombre_patologia)

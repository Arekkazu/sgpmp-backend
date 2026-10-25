# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
"""DTO de entrada de ``POST /infraestructuras/{id_infraestructura}/sensores`` (RF-49
Tipo B).
"""

from __future__ import annotations

from typing import Optional

from pydantic import field_validator

from src.shared.base_dto import BaseDTO
from src.shared.fechas import FechaHoraUtc


class AsociarSensorInfraestructuraDTO(BaseDTO):
    """RF-49 Tipo B (INC-M02-66-G90/#217): asociación AMBIENTAL a nivel de
    infraestructura -- `id_infraestructura` viene de la ruta, no del body, y
    no hay `tipo_activo`/`tipo_asociacion` porque este endpoint solo crea
    asociaciones AMBIENTAL (DIRECTA/POBLACIONAL son inherentemente por activo,
    ver `POST /activos-biologicos/{id_activo}/sensores`)."""

    dispositivo_iot_id: int
    sensor_id: int
    fecha_inicio: Optional[FechaHoraUtc] = None
    fecha_fin: Optional[FechaHoraUtc] = None
    motivo: Optional[str] = None

    @field_validator('motivo', mode='before')
    @classmethod
    def limpiar_motivo(cls, v: object) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None

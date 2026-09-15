from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import field_validator

from src.shared.base_dto import BaseDTO


class AsociarSensorInfraestructuraDTO(BaseDTO):
    """RF-49 Tipo B (INC-M02-66-G90/#217): asociación AMBIENTAL a nivel de
    infraestructura -- `id_infraestructura` viene de la ruta, no del body, y
    no hay `tipo_activo`/`tipo_asociacion` porque este endpoint solo crea
    asociaciones AMBIENTAL (DIRECTA/POBLACIONAL son inherentemente por activo,
    ver `POST /activos-biologicos/{id_activo}/sensores`)."""

    dispositivo_iot_id: int
    sensor_id: int
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None
    motivo: Optional[str] = None

    @field_validator('motivo', mode='before')
    @classmethod
    def limpiar_motivo(cls, v: object) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None

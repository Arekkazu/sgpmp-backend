from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import field_validator

from src.shared.base_dto import BaseDTO


class AsociarSensorActivoDTO(BaseDTO):
    tipo_activo: Literal['INDIVIDUAL', 'LOTE']
    # AMBIENTAL se retiró de este endpoint (INC-M02-39-G90 v2.0 / issue #351):
    # una asociación ambiental debe anclarse a la infraestructura, no a un
    # activo puntual del path. Ese caso ahora vive exclusivamente en
    # POST /infraestructuras/{id_infraestructura}/sensores.
    tipo_asociacion: Literal['DIRECTA', 'POBLACIONAL']
    dispositivo_iot_id: int
    sensor_id: int
    id_infraestructura: int
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

    @field_validator('fecha_fin', mode='before')
    @classmethod
    def validar_fecha_fin(cls, v: object) -> Optional[datetime]:
        return v  # La validación de coherencia fecha_inicio < fecha_fin se hace en el use case

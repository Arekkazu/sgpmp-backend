# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
"""DTO de entrada de ``POST /activos-biologicos/{id_activo}/sensores`` (RF-49)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import field_validator

from src.shared.base_dto import BaseDTO
from src.shared.fechas import FechaHoraUtc


class AsociarSensorActivoDTO(BaseDTO):
    """Asociación de un sensor a un activo.

    ``tipo_activo``: ``INDIVIDUAL`` | ``LOTE``. ``tipo_asociacion``: ``DIRECTA`` (sensor
    sobre el animal) | ``POBLACIONAL`` (sensor sobre el lote). Para asociaciones
    ambientales usar ``POST /infraestructuras/{id}/sensores``. ``fecha_fin`` debe
    ser posterior a ``fecha_inicio``.
    """
    tipo_activo: Literal['INDIVIDUAL', 'LOTE']
    # AMBIENTAL se retiró de este endpoint (INC-M02-39-G90 v2.0 / issue #351):
    # una asociación ambiental debe anclarse a la infraestructura, no a un
    # activo puntual del path. Ese caso ahora vive exclusivamente en
    # POST /infraestructuras/{id_infraestructura}/sensores.
    tipo_asociacion: Literal['DIRECTA', 'POBLACIONAL']
    dispositivo_iot_id: int
    sensor_id: int
    id_infraestructura: int
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

    @field_validator('fecha_fin', mode='before')
    @classmethod
    def validar_fecha_fin(cls, v: object) -> Optional[datetime]:
        return v  # La validación de coherencia fecha_inicio < fecha_fin se hace en el use case

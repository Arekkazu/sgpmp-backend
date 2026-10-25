# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
"""DTO de entrada de ``POST /activos-biologicos/{id_activo}/cierre`` (RF-38)."""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import field_validator

from src.shared.base_dto import BaseDTO
from src.shared.fechas import hoy_usuario

_MOTIVOS_VALIDOS = {'venta', 'sacrificio', 'muerte', 'finalizacion_lote', 'otro'}


class CerrarCicloDTO(BaseDTO):
    """Cierre del ciclo productivo.

    ``motivo_cierre``: ``venta`` | ``sacrificio`` | ``muerte`` | ``finalizacion_lote`` |
    ``otro``. ``fecha_cierre`` no puede ser futura.
    """
    fecha_cierre: date
    motivo_cierre: str
    descripcion_cierre: Optional[str] = None

    @field_validator('fecha_cierre')
    @classmethod
    def fecha_no_futura(cls, v: date) -> date:
        # La referencia es el día en la zona del usuario, no el del proceso (#411);
        # UTC si no la envía: ver src/shared/fechas.py.
        if v > hoy_usuario():
            raise ValueError('La fecha de cierre no puede ser futura.')
        return v

    @field_validator('motivo_cierre')
    @classmethod
    def motivo_no_vacio(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Debe indicar un motivo de cierre.')
        return v.strip()

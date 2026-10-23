# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-20 RF-33: fecha_nacimiento opcional y advertencia de edad (RFC-014) |
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
"""DTO de entrada de ``PATCH /activos-biologicos/{id_activo}`` (RF-35)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import ConfigDict, field_validator, model_validator

from src.shared.base_dto import BaseDTO
from src.shared.fechas import fecha_usuario, hoy_usuario
from src.shared.fechas import FechaHoraUtc


class ActualizarActivoIndividualDTO(BaseDTO):
    """Campos editables de un activo INDIVIDUAL; al menos uno es obligatorio.

    ``fecha_actualizacion`` debe ser la leída del activo (concurrencia optimista,
    412 si cambió). ``estado_activo`` no se acepta: el estado se cambia con
    ``PATCH /activos-biologicos/{id_activo}/estado`` (RF-44).
    """
    # INC-M02-G22: un campo no editable (estado, especie, tipo...) se ignoraba
    # en silencio y el PATCH respondía 200 sin aplicarlo. RF-35 exige impedir
    # esos cambios, no descartarlos.
    model_config = ConfigDict(extra='forbid')

    raza: Optional[str] = None
    sexo: Optional[str] = None
    fecha_nacimiento: Optional[FechaHoraUtc] = None
    peso_inicial: Optional[Decimal] = None
    # Concurrencia optimista (RF-35). Optional: la columna nace NULL sin
    # backfill, se establece recién en la primera edición del activo.
    fecha_actualizacion: Optional[FechaHoraUtc] = None
    # Declarado solo para rechazarlo con un mensaje que remita a RF-44, en vez
    # del genérico de extra='forbid'.
    estado_activo: Any = None

    @field_validator('estado_activo')
    @classmethod
    def estado_no_editable(cls, _valor: Any) -> Any:
        raise ValueError(
            'El estado del activo no se puede modificar en esta operación. '
            'Use el cambio de estado del activo (RF-44).'
        )

    @model_validator(mode='after')
    def al_menos_un_campo(self) -> ActualizarActivoIndividualDTO:
        if all(v is None for v in [self.raza, self.sexo, self.fecha_nacimiento, self.peso_inicial]):
            raise ValueError('Al menos un campo debe estar presente para actualizar.')
        return self

    @field_validator('fecha_nacimiento')
    @classmethod
    def fecha_nacimiento_no_futura(cls, valor: Optional[datetime]) -> Optional[datetime]:
        # RFC-014 (DEV-20): misma regla que el registro. Omitida (None) no cambia la fecha.
        if valor is not None and fecha_usuario(valor) > hoy_usuario():
            raise ValueError('fecha_nacimiento no puede ser futura.')
        return valor

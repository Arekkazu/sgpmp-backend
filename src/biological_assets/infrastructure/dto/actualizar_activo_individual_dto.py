from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import ConfigDict, field_validator, model_validator

from src.shared.base_dto import BaseDTO


class ActualizarActivoIndividualDTO(BaseDTO):
    # INC-M02-G22: un campo no editable (estado, especie, tipo...) se ignoraba
    # en silencio y el PATCH respondía 200 sin aplicarlo. RF-35 exige impedir
    # esos cambios, no descartarlos.
    model_config = ConfigDict(extra='forbid')

    raza: Optional[str] = None
    sexo: Optional[str] = None
    fecha_nacimiento: Optional[datetime] = None
    peso_inicial: Optional[Decimal] = None
    # Concurrencia optimista (RF-35). Optional: la columna nace NULL sin
    # backfill, se establece recién en la primera edición del activo.
    fecha_actualizacion: Optional[datetime] = None
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

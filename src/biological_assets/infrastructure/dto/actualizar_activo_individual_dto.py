from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import model_validator

from src.shared.base_dto import BaseDTO


class ActualizarActivoIndividualDTO(BaseDTO):
    raza: Optional[str] = None
    sexo: Optional[str] = None
    fecha_nacimiento: Optional[datetime] = None
    peso_inicial: Optional[Decimal] = None

    @model_validator(mode='after')
    def al_menos_un_campo(self) -> ActualizarActivoIndividualDTO:
        if all(v is None for v in [self.raza, self.sexo, self.fecha_nacimiento, self.peso_inicial]):
            raise ValueError('Al menos un campo debe estar presente para actualizar.')
        return self

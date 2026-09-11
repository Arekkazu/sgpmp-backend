"""DTO de entrada para editar un umbral ambiental (Flujo B — RF-17)."""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import field_validator

from src.shared.base_dto import BaseDTO
from .nivel_dto import NivelDTO

_NIVELES_REQUERIDOS = {'normal', 'precaucion', 'critico'}


class EditarUmbralDTO(BaseDTO):
    valor_min: Decimal
    valor_max: Decimal
    niveles: List[NivelDTO]
    fecha_actualizacion: Optional[datetime.datetime] = None

    @field_validator('valor_max')
    @classmethod
    def validar_rango(cls, v: Decimal, info) -> Decimal:
        min_ = info.data.get('valor_min')
        if min_ is not None and v <= min_:
            raise ValueError("valor_max debe ser estrictamente mayor que valor_min.")
        return v

    @field_validator('niveles')
    @classmethod
    def validar_niveles(cls, v: List[NivelDTO]) -> List[NivelDTO]:
        if len(v) != 3:
            raise ValueError("Se deben proporcionar exactamente 3 niveles de alerta (normal, precaucion, critico).")
        encontrados = {n.nivel for n in v}
        if encontrados != _NIVELES_REQUERIDOS:
            raise ValueError("Los niveles deben ser exactamente: normal, precaucion, critico.")
        return v

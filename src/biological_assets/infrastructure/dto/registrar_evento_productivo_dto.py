"""DTO de entrada de ``POST /activos-biologicos/{id_activo}/eventos/productivo``
(RF-43).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import Field, field_validator

from src.shared.base_dto import BaseDTO


class RegistrarEventoProductivoDTO(BaseDTO):
    """Producción registrada contra una métrica de la especie (M09, RF-16).

    ``id_metrica_produccion`` sale de ``GET /activos-biologicos/{id}/metricas`` y
    ``unidad_medida`` debe ser la de esa métrica.
    """
    id_metrica_produccion: int = Field(..., gt=0)
    # Cantidad > 0 se valida en el use case: RF-43 E-06 pide 422, no el 400 de Pydantic.
    cantidad_producida: Decimal
    unidad_medida: str
    fecha_evento: date
    condiciones_produccion: Optional[str] = None
    observaciones: Optional[str] = None

    @field_validator('unidad_medida')
    @classmethod
    def unidad_no_vacia(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('La unidad de medida no puede estar vacía.')
        return v

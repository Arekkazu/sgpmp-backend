# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RFC-021 RF-110 C21.1: entrada para declarar una arista de transmisión |
from __future__ import annotations

from decimal import Decimal
from typing import Literal, Optional

from pydantic import Field

from src.shared.base_dto import BaseDTO


class RegistrarAristaTransmisionDTO(BaseDTO):
    id_infraestructura_origen: int = Field(gt=0, description="Área desde la que puede salir el contagio.")
    id_infraestructura_destino: int = Field(gt=0, description="Área expuesta (misma finca).")
    via: Literal["PROXIMIDAD", "AIRE", "AGUA", "PERSONAL", "FOMITES", "ALIMENTO", "MOVIMIENTO_ANIMAL"]
    direccion: Literal["DIRIGIDA", "BIDIRECCIONAL"] = "DIRIGIDA"
    intensidad: Decimal = Field(gt=0, le=1, max_digits=4, decimal_places=3,
                                description="Qué tanto transmite la vía, de 0 (exclusivo) a 1.")
    factor_barrera: Decimal = Field(default=Decimal("1"), ge=0, le=1, max_digits=4, decimal_places=3,
                                    description="1 sin barrera; 0 barrera total.")
    descripcion: Optional[str] = Field(default=None, max_length=200)

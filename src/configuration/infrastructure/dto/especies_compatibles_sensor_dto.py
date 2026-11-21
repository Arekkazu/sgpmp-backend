# | Fecha      | Nombre   | Que se hizo                                                      |
# |------------|----------|------------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M03-135-G01 RF-49: especies compatibles de un sensor desde M09 |
from __future__ import annotations

from pydantic import Field

from src.shared.base_dto import BaseDTO


class EspeciesCompatiblesSensorDTO(BaseDTO):
    ids_especies: list[int] = Field(..., min_length=1, max_length=50,
                                    description="Especies compatibles; reemplaza la lista vigente.")

"""DTO de entrada para asignar/desasignar fincas a un usuario (RF-25)."""
from __future__ import annotations

from pydantic import Field

from src.shared.base_dto import BaseDTO


class AsignarFincasDTO(BaseDTO):
    ids_fincas: list[int] = Field(default_factory=list)

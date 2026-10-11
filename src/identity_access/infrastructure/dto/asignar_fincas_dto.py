"""DTO de entrada para asignar/desasignar fincas a un usuario (RF-25)."""
from __future__ import annotations

from pydantic import Field

from src.shared.base_dto import BaseDTO


class AsignarFincasDTO(BaseDTO):
    """Conjunto completo de fincas del usuario; lo que no venga se desasigna."""
    ids_fincas: list[int] = Field(default_factory=list)

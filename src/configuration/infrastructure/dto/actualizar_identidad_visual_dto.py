"""DTO de entrada para actualizar la identidad visual de una finca (PATCH RF-26).

Incluye ``version`` para control de concurrencia optimista.
"""
from pydantic import Field

from src.shared.base_dto import BaseDTO


class ActualizarIdentidadVisualDTO(BaseDTO):
    primary_color: str = Field(pattern=r'^#[0-9A-Fa-f]{6}$')
    secondary_color: str = Field(pattern=r'^#[0-9A-Fa-f]{6}$')
    org_display_name: str = Field(min_length=1, max_length=50)
    version: int

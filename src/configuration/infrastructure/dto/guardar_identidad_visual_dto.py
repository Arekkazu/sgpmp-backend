"""DTO de entrada para crear la identidad visual institucional de una finca (POST RF-26).

Se usa junto con un ``UploadFile`` opcional para el logo (multipart/form-data).
"""
from pydantic import Field

from src.shared.base_dto import BaseDTO


class GuardarIdentidadVisualDTO(BaseDTO):
    id_finca: int
    primary_color: str = Field(pattern=r'^#[0-9A-Fa-f]{6}$')
    secondary_color: str = Field(pattern=r'^#[0-9A-Fa-f]{6}$')
    org_display_name: str = Field(min_length=1, max_length=50)

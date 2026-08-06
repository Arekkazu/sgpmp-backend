"""DTO de entrada para corregir un reporte consolidado NIC-41 (RF-79 E4)."""
from __future__ import annotations

from pydantic import Field

from src.shared.base_dto import BaseDTO


class CorregirProvisionDTO(BaseDTO):
    """Motivo obligatorio de la corrección de un reporte consolidado."""

    motivo_correccion: str = Field(min_length=20, max_length=500)

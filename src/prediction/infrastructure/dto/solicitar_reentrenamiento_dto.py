# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-31 | Arekkazu | RF-71/RF-73: solicitud de reentrenamiento como evento de auditoría |
from __future__ import annotations

from typing import Optional

from pydantic import Field

from src.shared.base_dto import BaseDTO


class SolicitarReentrenamientoDTO(BaseDTO):
    tipo_modelo: str = Field(description="MODELO_ESPECIES_GRANDES o MODELO_ESPECIES_MEDIANAS")
    motivo: Optional[str] = Field(default=None, max_length=500)

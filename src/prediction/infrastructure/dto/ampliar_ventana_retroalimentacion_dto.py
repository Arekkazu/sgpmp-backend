# | Fecha      | Nombre   | Que se hizo                                                  |
# |------------|----------|--------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M04-229-G070 RF-72: ampliación de ventana por resultado  |
from __future__ import annotations

import uuid

from pydantic import Field

from src.shared.base_dto import BaseDTO


class AmpliarVentanaRetroalimentacionDTO(BaseDTO):
    id_resultado_inferencia: uuid.UUID
    dias_habilitados: int = Field(..., ge=1, le=365, description="Días que el resultado queda habilitado desde hoy.")
    justificacion: str = Field(..., min_length=10, max_length=1000, description="Motivo técnico de la excepción (RF-73).")

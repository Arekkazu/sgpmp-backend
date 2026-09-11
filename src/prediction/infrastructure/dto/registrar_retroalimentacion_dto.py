from __future__ import annotations

import uuid
from typing import Optional

from pydantic import Field

from src.shared.base_dto import BaseDTO


class RegistrarRetroalimentacionDTO(BaseDTO):
    id_resultado_inferencia: uuid.UUID
    id_activo_biologico: int
    estado_retroalimentacion: str
    diagnosticos_reales: Optional[list[int]] = Field(None, max_length=3)
    observaciones_clinicas: Optional[str] = None
    fuente_diagnostico: Optional[str] = None

# | Fecha      | Nombre   | Que se hizo                                                      |
# |------------|----------|------------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M04-227-G067 RF-72: estado sin coerción, lo valida el dominio |
from __future__ import annotations

import uuid
from typing import Any, Optional

from pydantic import Field

from src.shared.base_dto import BaseDTO


class RegistrarRetroalimentacionDTO(BaseDTO):
    id_resultado_inferencia: uuid.UUID
    id_activo_biologico: int
    # INC-M04-227-G067: sin tipo para que un número o null lleguen al dominio y respondan
    # 422 ESTADO_RETROALIMENTACION_INVALIDO (RF-72 E3), no el VAL_ENTRADA de Pydantic.
    estado_retroalimentacion: Any = Field(..., description="CORRECTO, PARCIAL, INCORRECTO o SIN_EVENTO, en mayúsculas.")
    diagnosticos_reales: Optional[list[int]] = Field(None, max_length=3)
    observaciones_clinicas: Optional[str] = None
    fuente_diagnostico: Optional[str] = None

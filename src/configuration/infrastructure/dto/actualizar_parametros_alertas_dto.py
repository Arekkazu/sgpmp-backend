# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-168-G76 RF-57: cuerpo del PATCH de parámetros de alertas |
from __future__ import annotations

from typing import Any

from pydantic import Field

from src.shared.base_dto import BaseDTO


class ActualizarParametrosAlertasDTO(BaseDTO):
    """``{"parametros": {"umbral_confianza_edge_ia": 0.80}}``: solo los parámetros que cambian.

    Tipos y rangos los valida DEV-14 (p. ej. umbral_confianza_edge_ia entre 0.70 y 0.95).
    """

    parametros: dict[str, Any] = Field(..., min_length=1)

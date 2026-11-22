# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-167-G75 RF-57 E16: resultado de la reevaluación por IA |
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from pydantic import Field, field_validator

from src.shared.base_dto import BaseDTO

_SEVERIDADES = {"LEVE", "MODERADO", "CRITICO"}
_TIPOS = {"ESTRES_TERMICO", "SINDROME_RESPIRATORIO", "RIESGO_HIDRICO", "FIEBRE", "INACTIVIDAD_ANORMAL",
          "PREDICCION_PATOLOGIA"}


class ReevaluarAlertaDTO(BaseDTO):
    """Lo que devuelve el motor de inferencia al reevaluar el evento original de la alerta (E16)."""

    severidad_ia: str = Field(..., min_length=2, max_length=20)
    tipo_alerta_ia: Optional[str] = Field(default=None, description="Sin valor: el tipo de la alerta original.")
    probabilidad_ia: Optional[Decimal] = Field(default=None, ge=0, le=1)
    id_paquete_inferencia: Optional[int] = Field(default=None, gt=0)
    metadata_reevaluacion: Optional[dict[str, Any]] = None

    @field_validator("severidad_ia")
    @classmethod
    def validar_severidad(cls, v: str) -> str:
        v = v.upper().strip()
        if v not in _SEVERIDADES:
            raise ValueError(f"severidad_ia debe ser uno de: {', '.join(sorted(_SEVERIDADES))}")
        return v

    @field_validator("tipo_alerta_ia")
    @classmethod
    def validar_tipo(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.upper().strip()
        if v not in _TIPOS:
            raise ValueError(f"tipo_alerta_ia debe ser uno de: {', '.join(sorted(_TIPOS))}")
        return v

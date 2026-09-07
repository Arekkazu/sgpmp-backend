"""Schemas de respuesta para los endpoints de umbrales ambientales (RF-17)."""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any, List, Optional

from pydantic import BaseModel, field_validator


class NivelAlertaResponse(BaseModel):
    nivel: str
    limite_inferior: Decimal
    limite_superior: Decimal

    model_config = {'from_attributes': True}

    @field_validator('nivel', mode='before')
    @classmethod
    def extraer_nivel(cls, v: object) -> str:
        if hasattr(v, 'value'):
            return v.value  # type: ignore[attr-defined]
        return str(v)


class UmbralAmbientalResponse(BaseModel):
    id_umbral_ambiental: int
    id_especie: int
    id_variable_ambiental: int
    unidad_medida: str
    valor_min: Decimal
    valor_max: Decimal
    es_activo: bool
    fecha_actualizacion: Optional[datetime.datetime]
    niveles: List[NivelAlertaResponse]

    model_config = {'from_attributes': True}


class UmbralesPorEspecieResponse(BaseModel):
    total: int
    items: List[UmbralAmbientalResponse]


class VariableAmbientalResponse(BaseModel):
    """Catálogo de variables ambientales (`modulo9.variables_ambientales`)."""

    id_variable_ambiental: int
    nombre: str
    unidad: str
    valor_fisico_min: Decimal
    valor_fisico_max: Decimal

    model_config = {'from_attributes': True}


class VariablesAmbientalesResponse(BaseModel):
    total: int
    items: List[VariableAmbientalResponse]


class AuditoriaUmbralResponse(BaseModel):
    """Registro de auditoría de un umbral ambiental (RF-17, TC-M09-64)."""

    id_auditoria_umbral: int
    id_umbral_ambiental: int
    id_usuario: Optional[int]
    tipo_operacion: str
    valores_anteriores: Optional[dict[str, Any]]
    valores_nuevos: dict[str, Any]
    fecha_gestion: datetime.datetime

    model_config = {'from_attributes': True}


class AuditoriaUmbralesResponse(BaseModel):
    total: int
    items: List[AuditoriaUmbralResponse]

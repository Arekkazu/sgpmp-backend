# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-31 | Arekkazu | USAB-M03-M04 T-18 RF-62: sensor y lectura por nombre en calidad |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo y schemas |
"""Schemas de respuesta de la calidad de telemetría (RF-62).

Expone las evaluaciones, el listado paginado y el resumen de una reevaluación,
con el sensor y la lectura resueltos por nombre.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TelemetriaCalidadSchema(BaseModel):
    """Evaluación de calidad de una lectura con nombres legibles."""

    model_config = ConfigDict(from_attributes=True)

    id_evaluacion: UUID
    id_telemetria: int
    id_sensor: int
    timestamp_evaluacion: datetime
    indice_calidad: Optional[int]
    clasificacion_calidad: str
    apto_para_ia: bool
    apto_para_nic41: bool
    flags_detectados: dict
    version_limites_fisicos_aplicada: Optional[str]
    parametros_aplicados: dict
    parametros_calibracion_aplicados: Optional[dict]
    estado_evaluacion: str
    motivo_reevaluacion: Optional[str]
    id_evaluacion_superada: Optional[UUID]
    version_evaluacion: Optional[str]
    fecha_creacion: Optional[datetime]
    # T-18: la lectura y el sensor salían como "#117088"; nombres resueltos en el router.
    nombre_sensor: Optional[str] = None
    nombre_variable: Optional[str] = None
    valor_lectura: Optional[float] = None
    unidad_lectura: Optional[str] = None


class ListaCalidadSchema(BaseModel):
    """Página de evaluaciones de calidad."""

    total: int
    pagina: int
    por_pagina: int
    items: list[TelemetriaCalidadSchema]


class ReevaluacionResponseSchema(BaseModel):
    """Resumen de una reevaluación: evaluaciones superadas y creadas."""

    evaluaciones_superadas: int
    evaluaciones_creadas: int

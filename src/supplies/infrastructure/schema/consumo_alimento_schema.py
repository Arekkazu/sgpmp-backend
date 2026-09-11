"""Schemas de respuesta para los endpoints de consumo de alimento (RF-75)."""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class ConsumoAlimentoResponse(BaseModel):
    """Datos de un registro de consumo de alimento retornados por el sistema."""

    id_consumo_alimeto: int
    id_activo_biologico: int
    id_tipo_alimento: int
    tipo_alimento: str
    tipo_unidad: str
    cantidad_suministrada: Decimal
    costo_unitario: Optional[Decimal]
    costo_total: Optional[Decimal]
    consumo_por_individuo_kg: Optional[Decimal]
    observacion: Optional[str]
    fecha_consumo: Optional[datetime.date]
    hora_suministro: Optional[datetime.time]
    estado_registro: str
    id_usuario: Optional[int]
    fecha_registro: Optional[datetime.datetime]
    justificacion_anulacion: Optional[str]
    fecha_hora_anulacion: Optional[datetime.datetime]

    model_config = {"from_attributes": True}


class ConsultaConsumosResponse(BaseModel):
    """Resultado de la búsqueda de registros de consumo."""

    total: int
    items: list[ConsumoAlimentoResponse]

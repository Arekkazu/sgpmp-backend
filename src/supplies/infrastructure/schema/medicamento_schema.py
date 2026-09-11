"""Schemas de respuesta para los endpoints de aplicación de medicamento (RF-76)."""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class MedicamentoResponse(BaseModel):
    """Datos de un registro de aplicación de medicamento retornados por el sistema."""

    id_registro_medicamento: int
    id_activo_biologico: int
    nombre_medicamento: str
    via_aplicacion: Optional[str]
    unidad_dosis: str
    cantidad: Decimal
    dosis_por_individuo: Optional[Decimal]
    fecha_aplicacion: datetime.date
    hora_aplicacion: Optional[datetime.time]
    periodo_retiro_dias: Optional[int]
    fecha_fin_retiro: Optional[datetime.date]
    costo_unitario_medicamento: Decimal
    costo_total_medicamento: Optional[Decimal]
    motivo_aplicacion: Optional[str]
    id_evento_sanitario: Optional[int]
    nombre_veterinario: Optional[str]
    id_usuario: int
    id_usuario_veterinario: Optional[int]
    estado_registro: str
    fecha_registro: Optional[datetime.datetime]
    justificacion_anulacion: Optional[str]
    fecha_hora_anulacion: Optional[datetime.datetime]

    model_config = {"from_attributes": True}


class RegistroMedicamentoResponse(BaseModel):
    """Respuesta del registro de un medicamento, con el período de retiro vigente."""

    medicamento: MedicamentoResponse
    fecha_fin_retiro_vigente: Optional[datetime.date]
    mensaje: str


class ConsultaMedicamentosResponse(BaseModel):
    """Resultado de la búsqueda de registros de aplicación de medicamento."""

    total: int
    items: list[MedicamentoResponse]

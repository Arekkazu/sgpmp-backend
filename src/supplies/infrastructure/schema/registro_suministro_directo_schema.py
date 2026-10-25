# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-78: estado YA_PROCESADO/YA_ACUMULADO   |
"""Schema de respuesta para los endpoints de registro directo de suministro (RF-78)."""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class RegistroSuministroDirectoResponse(BaseModel):
    """Datos de un registro directo de suministro (SERVICIO_VETERINARIO/INSEMINACION/CORRECCION)."""

    id_registro_suministro: Optional[UUID]
    id_activo_biologico: int
    id_ciclo_productivo: int
    id_gestion_fases: Optional[int]
    tipo_suministro: str
    cantidad: Decimal
    unidad_medida: str
    precio_unitario_resuelto: Decimal
    costo_registro: Decimal
    origen_precio: str
    fecha_aplicacion: datetime.date
    naturaleza_costo: str
    justificacion_precio: Optional[str]
    observacion: Optional[str]
    tipo_operacion: str
    id_registro_original: Optional[UUID]
    motivo_correccion: Optional[str]
    id_idempotencia: Optional[UUID]
    id_registro_rf75: Optional[UUID] = None
    id_registro_rf76: Optional[UUID] = None
    fecha_registro: Optional[datetime.datetime]

    model_config = {"from_attributes": True}


class ResultadoRegistroSuministroResponse(BaseModel):
    """Respuesta de RF-78: ``REGISTRADO``, ``YA_PROCESADO`` (E8) o ``YA_ACUMULADO`` (Fase 1b)."""

    estado: str
    id_registro_suministro: Optional[UUID]
    mensaje: str
    registro: RegistroSuministroDirectoResponse

    @classmethod
    def desde_resultado(cls, resultado) -> "ResultadoRegistroSuministroResponse":
        registro = RegistroSuministroDirectoResponse.model_validate(resultado.registro)
        return cls(
            estado=resultado.estado,
            id_registro_suministro=registro.id_registro_suministro,
            mensaje=resultado.mensaje,
            registro=registro,
        )

# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-28 | Arekkazu | BE-0 RF-55: respuesta del CRUD de reglas de alerta |
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field

from src.telemetry.infrastructure.schema.sincronizacion_regla_edge_schema import SincronizacionReglaSchema


class ReglaAlertaResponse(BaseModel):
    id_regla_alertas: int
    nombre: str
    descripcion: Optional[str] = None
    tipo_sensor: str
    categoria_variable: Optional[str] = None
    es_regla_compuesta: bool
    umbral_min: Optional[Decimal] = None
    umbral_max: Optional[Decimal] = None
    umbrales_severidad: Optional[dict[str, Any]] = None
    ventana_confirmacion_min: Decimal
    lectura_confirmacion_max: Decimal
    mensaje: Optional[str] = None
    id_finca: Optional[int] = None
    id_especie: Optional[int] = None
    es_activa: bool
    tiene_ejecutar_edge: bool
    version_regla: int = Field(description="La sube la BD cuando cambia lo que recibe el Gateway Edge.")
    id_usuario: Optional[int] = None
    fecha_creacion: datetime
    fecha_actualizacion: Optional[datetime] = Field(
        default=None, description="Enviarla tal cual en el PUT (concurrencia optimista, 412)."
    )
    sincronizacion_edge: Optional[SincronizacionReglaSchema] = Field(
        default=None,
        description="Resultado de propagar la regla a sus Gateway Edge; solo compuestas con tiene_ejecutar_edge.",
    )

    model_config = {'from_attributes': True}

    @classmethod
    def de(cls, regla: Any, sincronizacion: Any = None) -> "ReglaAlertaResponse":
        respuesta = cls.model_validate(regla)
        if sincronizacion is not None:
            respuesta.sincronizacion_edge = SincronizacionReglaSchema.model_validate(sincronizacion)
        return respuesta

"""Schema de respuesta para los endpoints de parámetros operativos (RF-18)."""
from __future__ import annotations

import datetime

from pydantic import BaseModel


class ConfiguracionGlobalResponse(BaseModel):
    id_configuracion_global: int
    frecuencia_muestreo: int
    heartbeat: int
    fecha_actualizacion: datetime.datetime
    id_usuario: int
    es_activo: bool

    model_config = {"from_attributes": True}

    @classmethod
    def from_entity(cls, config) -> ConfiguracionGlobalResponse:
        return cls(
            id_configuracion_global=config.id_configuracion_global,
            frecuencia_muestreo=config.frecuencia_muestreo.valor,
            heartbeat=config.heartbeat.valor,
            fecha_actualizacion=config.fecha_actualizacion,
            id_usuario=config.id_usuario,
            es_activo=config.es_activo,
        )

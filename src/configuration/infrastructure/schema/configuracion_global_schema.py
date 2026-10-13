"""Schema de respuesta para los endpoints de parámetros operativos (RF-18)."""
from __future__ import annotations

import datetime

from typing import Optional

from pydantic import BaseModel


class ConfiguracionGlobalResponse(BaseModel):
    """Configuración operativa global (minutos de muestreo y heartbeat)."""
    id_configuracion_global: int
    frecuencia_muestreo: int
    heartbeat: int
    fecha_actualizacion: datetime.datetime
    id_usuario: int
    #: Quién hizo la última actualización, para no mostrar "usuario #29".
    nombre_usuario: Optional[str] = None
    es_activo: bool

    model_config = {"from_attributes": True}

    @classmethod
    def from_entity(cls, config, nombre_usuario: Optional[str] = None) -> ConfiguracionGlobalResponse:
        return cls(
            id_configuracion_global=config.id_configuracion_global,
            frecuencia_muestreo=config.frecuencia_muestreo.valor,
            heartbeat=config.heartbeat.valor,
            fecha_actualizacion=config.fecha_actualizacion,
            id_usuario=config.id_usuario,
            nombre_usuario=nombre_usuario,
            es_activo=config.es_activo,
        )

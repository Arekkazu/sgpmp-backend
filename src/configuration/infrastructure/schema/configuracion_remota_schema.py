"""Schemas de respuesta para endpoints de configuración remota de dispositivos IoT (RF-23)."""
from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel


class ConfiguracionRemotaResponse(BaseModel):
    id_configuracion_remota: int
    id_dispositivo_iot: int
    frecuencia_captura: int
    intervalo_transmision: int
    estado: str
    id_usuario: Optional[int]
    fecha_creacion: Optional[datetime.datetime]
    fecha_aplicacion: Optional[datetime.datetime]
    mensaje: Optional[str] = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_entity(cls, config, mensaje: Optional[str] = None) -> ConfiguracionRemotaResponse:
        return cls(
            id_configuracion_remota=config.id_configuracion_remota,
            id_dispositivo_iot=config.id_dispositivo_iot,
            frecuencia_captura=config.frecuencia_captura,
            intervalo_transmision=config.intervalo_transmision,
            estado=config.estado,
            id_usuario=config.id_usuario,
            fecha_creacion=config.fecha_creacion,
            fecha_aplicacion=config.fecha_aplicacion,
            mensaje=mensaje,
        )


class ListaConfiguracionesRemotasResponse(BaseModel):
    total: int
    items: list[ConfiguracionRemotaResponse]

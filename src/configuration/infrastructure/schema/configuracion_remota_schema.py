"""Schemas de respuesta para endpoints de configuración remota de dispositivos IoT (RF-23)."""
from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel


class ConfiguracionRemotaResponse(BaseModel):
    """Configuración remota enviada y su estado (PENDIENTE, APLICADA, NO_CONF,
    CANCELADA). Un SENSOR trae ``frecuencia_captura`` e ``intervalo_transmision``
    (``fps`` nulo); una CAMARA trae ``fps`` (los otros dos nulos), RF-23 v1.1.
    """
    id_configuracion_remota: int
    id_dispositivo_iot: int
    frecuencia_captura: Optional[int]
    intervalo_transmision: Optional[int]
    fps: Optional[int] = None
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
            fps=config.fps,
            estado=config.estado,
            id_usuario=config.id_usuario,
            fecha_creacion=config.fecha_creacion,
            fecha_aplicacion=config.fecha_aplicacion,
            mensaje=mensaje,
        )


class ListaConfiguracionesRemotasResponse(BaseModel):
    """Historial de configuraciones remotas de un dispositivo."""
    total: int
    items: list[ConfiguracionRemotaResponse]

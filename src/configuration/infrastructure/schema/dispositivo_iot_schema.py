"""Schemas de respuesta para endpoints de dispositivos IoT (RF-21)."""
from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel


class DispositivoIotResponse(BaseModel):
    id_dispositivo_iot: int
    serial: str
    descripcion: str
    id_infraestructura: int
    id_tipo_dispositivo: int
    es_activo: bool
    fecha_creacion: datetime.datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_entity(cls, dispositivo) -> DispositivoIotResponse:
        return cls(
            id_dispositivo_iot=dispositivo.id_dispositivo_iot,
            serial=dispositivo.serial.valor,
            descripcion=dispositivo.descripcion,
            id_infraestructura=dispositivo.id_infraestructura,
            id_tipo_dispositivo=dispositivo.id_tipo_dispositivo,
            es_activo=dispositivo.es_activo,
            fecha_creacion=dispositivo.fecha_creacion,
        )


class ListaDispositivosIotResponse(BaseModel):
    total: int
    items: list[DispositivoIotResponse]

"""Schemas de respuesta para endpoints de dispositivos IoT (RF-21)."""
from __future__ import annotations

import datetime
from decimal import Decimal
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
    id_dispositivo_gateway: Optional[int] = None
    resolucion: Optional[str] = None
    fps: Optional[int] = None
    area_cobertura_m2: Optional[Decimal] = None

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
            id_dispositivo_gateway=dispositivo.id_dispositivo_gateway,
            resolucion=dispositivo.resolucion,
            fps=dispositivo.fps,
            area_cobertura_m2=dispositivo.area_cobertura_m2,
        )


class ListaDispositivosIotResponse(BaseModel):
    total: int
    items: list[DispositivoIotResponse]

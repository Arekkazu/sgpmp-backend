"""Schemas de respuesta para endpoints de asociaciones sensor-área (RF-22)."""
from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel


class SensorAreaResponse(BaseModel):
    id_sensores_area_asociada: int
    id_sensor: int
    id_dispositivo_iot: int
    id_infraestructura: int
    punto_instalacion: str
    tiene_estado: bool
    fecha_asociacion: datetime.datetime
    fecha_finalizacion: Optional[datetime.datetime]
    id_usuario: int

    model_config = {"from_attributes": True}

    @classmethod
    def from_entity(cls, sensor_area) -> SensorAreaResponse:
        return cls(
            id_sensores_area_asociada=sensor_area.id_sensores_area_asociada,
            id_sensor=sensor_area.id_sensor,
            id_dispositivo_iot=sensor_area.id_dispositivo_iot,
            id_infraestructura=sensor_area.id_infraestructura,
            punto_instalacion=sensor_area.punto_instalacion.valor,
            tiene_estado=sensor_area.tiene_estado,
            fecha_asociacion=sensor_area.fecha_asociacion,
            fecha_finalizacion=sensor_area.fecha_finalizacion,
            id_usuario=sensor_area.id_usuario,
        )


class ListaSensorAreasResponse(BaseModel):
    total: int
    items: list[SensorAreaResponse]

"""Schemas de respuesta para endpoints de asociaciones sensor-área (RF-22)."""
from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel


class SensorAreaResponse(BaseModel):
    """Asociación sensor-área; ``tiene_estado`` true = vigente."""
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


class AsociacionActivoSuperadaResponse(BaseModel):
    """Asociación sensor→activo de M02 cerrada por la reasignación del sensor."""
    id_asociacion_activo_sensor: int
    id_activo_biologico: Optional[int]
    tipo: str


class AsociarSensorAreaResponse(SensorAreaResponse):
    """Respuesta de POST /sensores/{id}/asociar.

    Issue #290: si fue una reasignación de área, `asociaciones_activo_superadas`
    lista las asociaciones sensor→activo AMBIENTAL/POBLACIONAL que quedaron
    SUPERADA, para que el cliente avise al usuario y este re-asocie vía RF-49
    si lo desea. Vacía en una primera asociación o si no había ninguna.
    """

    asociaciones_activo_superadas: list[AsociacionActivoSuperadaResponse] = []

    @classmethod
    def from_resultado(cls, sensor_area, superadas) -> AsociarSensorAreaResponse:
        return cls(
            **SensorAreaResponse.from_entity(sensor_area).model_dump(),
            asociaciones_activo_superadas=[
                AsociacionActivoSuperadaResponse(
                    id_asociacion_activo_sensor=s.id_asociacion_activo_sensor,
                    id_activo_biologico=s.id_activo_biologico,
                    tipo=s.tipo,
                )
                for s in superadas
            ],
        )


class ListaSensorAreasResponse(BaseModel):
    """Historial de asociaciones sensor-área."""
    total: int
    items: list[SensorAreaResponse]

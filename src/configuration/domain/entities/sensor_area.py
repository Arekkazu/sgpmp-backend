"""Entidad de dominio ``SensorArea`` — asociación activa entre sensor y área productiva (RF-22).

`tiene_estado=True` indica asociación activa. `terminar()` cierra la asociación
estableciendo la fecha de finalización (flujo de reasignación).
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Optional

from src.configuration.domain.value_objects.punto_instalacion import PuntoInstalacion


@dataclass(eq=False)
class SensorArea:
    id_sensor: int
    id_dispositivo_iot: int
    id_infraestructura: int
    punto_instalacion: PuntoInstalacion
    tiene_estado: bool
    fecha_asociacion: datetime.datetime
    id_usuario: int
    id_sensores_area_asociada: Optional[int] = None
    fecha_finalizacion: Optional[datetime.datetime] = None

    @classmethod
    def crear(
        cls,
        *,
        id_sensor: int,
        id_dispositivo_iot: int,
        id_infraestructura: int,
        punto_instalacion: PuntoInstalacion,
        id_usuario: int,
    ) -> SensorArea:
        return cls(
            id_sensor=id_sensor,
            id_dispositivo_iot=id_dispositivo_iot,
            id_infraestructura=id_infraestructura,
            punto_instalacion=punto_instalacion,
            tiene_estado=True,
            fecha_asociacion=datetime.datetime.now(datetime.timezone.utc),
            id_usuario=id_usuario,
        )

    def terminar(self) -> None:
        self.tiene_estado = False
        self.fecha_finalizacion = datetime.datetime.now(datetime.timezone.utc)

    def _snapshot(self) -> dict:
        return {
            "id_sensor": self.id_sensor,
            "id_dispositivo_iot": self.id_dispositivo_iot,
            "id_infraestructura": self.id_infraestructura,
            "punto_instalacion": self.punto_instalacion.valor,
            "tiene_estado": self.tiene_estado,
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SensorArea):
            return NotImplemented
        if self.id_sensores_area_asociada is None or other.id_sensores_area_asociada is None:
            return self is other
        return self.id_sensores_area_asociada == other.id_sensores_area_asociada

    def __hash__(self) -> int:
        return hash(self.id_sensores_area_asociada)

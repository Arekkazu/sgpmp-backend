"""Entidad de dominio ``Calibracion`` — registro de calibración de un sensor (RF-24).

Es inmutable una vez creada; la tabla `calibraciones` es el historial de trazabilidad.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass(eq=False)
class Calibracion:
    id_dispositivo_iot: int
    id_sensor: int
    valor_referencia: Decimal
    fecha_calibracion: datetime.datetime
    id_usuario: int
    id_calibracion: Optional[int] = None
    observaciones: Optional[str] = None

    @classmethod
    def crear(
        cls,
        *,
        id_dispositivo_iot: int,
        id_sensor: int,
        valor_referencia: Decimal,
        fecha_calibracion: datetime.datetime,
        id_usuario: int,
        observaciones: Optional[str] = None,
    ) -> Calibracion:
        return cls(
            id_dispositivo_iot=id_dispositivo_iot,
            id_sensor=id_sensor,
            valor_referencia=valor_referencia,
            fecha_calibracion=fecha_calibracion,
            id_usuario=id_usuario,
            observaciones=observaciones,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Calibracion):
            return NotImplemented
        if self.id_calibracion is None or other.id_calibracion is None:
            return self is other
        return self.id_calibracion == other.id_calibracion

    def __hash__(self) -> int:
        return hash(self.id_calibracion)

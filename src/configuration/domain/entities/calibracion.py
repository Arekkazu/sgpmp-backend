"""Entidad de dominio ``Calibracion`` — registro de calibración de un sensor (RF-24).

Es inmutable una vez creada; la tabla `calibraciones` es el historial de trazabilidad.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from src.configuration.domain.value_objects.modo_calibracion import ModoCalibracion


@dataclass(eq=False)
class Calibracion:
    """Calibración de un sensor (RF-24); inmutable, cada nueva calibración es un registro más del historial.

    ``ganancia`` y ``offset`` son los parámetros de corrección que se envían al dispositivo.
    """
    id_dispositivo_iot: int
    id_sensor: int
    valor_referencia: Decimal
    fecha_calibracion: datetime.datetime
    id_usuario: int
    ganancia: Decimal = Decimal("1.0")
    offset: Decimal = Decimal("0")
    id_calibracion: Optional[int] = None
    observaciones: Optional[str] = None
    modo_calibracion: ModoCalibracion = ModoCalibracion.SENSOR

    @classmethod
    def crear(
        cls,
        *,
        id_dispositivo_iot: int,
        id_sensor: int,
        valor_referencia: Decimal,
        fecha_calibracion: datetime.datetime,
        id_usuario: int,
        ganancia: Decimal = Decimal("1.0"),
        offset: Optional[Decimal] = None,
        observaciones: Optional[str] = None,
        modo_calibracion: ModoCalibracion = ModoCalibracion.SENSOR,
    ) -> Calibracion:
        # offset por defecto = valor_referencia (ajuste de cero), consistente con
        # el consumidor de telemetry cuando el modelo era de un solo parámetro.
        return cls(
            id_dispositivo_iot=id_dispositivo_iot,
            id_sensor=id_sensor,
            valor_referencia=valor_referencia,
            fecha_calibracion=fecha_calibracion,
            id_usuario=id_usuario,
            ganancia=ganancia,
            offset=offset if offset is not None else valor_referencia,
            observaciones=observaciones,
            modo_calibracion=modo_calibracion,
        )

    def _snapshot(self) -> dict:
        """Estado JSON-serializable para el historial de auditoría (RF-10)."""
        return {
            "id_dispositivo_iot": self.id_dispositivo_iot,
            "id_sensor": self.id_sensor,
            "valor_referencia": str(self.valor_referencia),
            "ganancia": str(self.ganancia),
            "offset": str(self.offset),
            "fecha_calibracion": self.fecha_calibracion.isoformat(),
            "id_usuario": self.id_usuario,
            "observaciones": self.observaciones,
            "modo_calibracion": self.modo_calibracion.value,
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Calibracion):
            return NotImplemented
        if self.id_calibracion is None or other.id_calibracion is None:
            return self is other
        return self.id_calibracion == other.id_calibracion

    def __hash__(self) -> int:
        return hash(self.id_calibracion)

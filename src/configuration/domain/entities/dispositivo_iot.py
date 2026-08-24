"""Entidad de dominio ``DispositivoIot`` — dispositivo IoT registrado en una finca (RF-21)."""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Optional

from src.configuration.domain.value_objects.serial_dispositivo import SerialDispositivo


@dataclass(eq=False)
class DispositivoIot:
    serial: SerialDispositivo
    descripcion: str
    id_infraestructura: int
    id_tipo_dispositivo: int
    es_activo: bool
    fecha_creacion: datetime.datetime
    id_dispositivo_iot: Optional[int] = None

    @classmethod
    def crear(
        cls,
        *,
        serial: SerialDispositivo,
        descripcion: str,
        id_infraestructura: int,
        id_tipo_dispositivo: int,
        es_activo: bool = True,
    ) -> DispositivoIot:
        return cls(
            serial=serial,
            descripcion=descripcion,
            id_infraestructura=id_infraestructura,
            id_tipo_dispositivo=id_tipo_dispositivo,
            es_activo=es_activo,
            fecha_creacion=datetime.datetime.now(datetime.timezone.utc),
        )

    def desactivar(self) -> None:
        self.es_activo = False

    def _snapshot(self) -> dict:
        return {
            "serial": self.serial.valor,
            "descripcion": self.descripcion,
            "id_infraestructura": self.id_infraestructura,
            "id_tipo_dispositivo": self.id_tipo_dispositivo,
            "es_activo": self.es_activo,
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DispositivoIot):
            return NotImplemented
        if self.id_dispositivo_iot is None or other.id_dispositivo_iot is None:
            return self is other
        return self.id_dispositivo_iot == other.id_dispositivo_iot

    def __hash__(self) -> int:
        return hash(self.id_dispositivo_iot)

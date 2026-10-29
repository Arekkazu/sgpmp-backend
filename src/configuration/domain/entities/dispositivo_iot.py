"""Entidad de dominio ``DispositivoIot`` — dispositivo IoT registrado en una finca (RF-21)."""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from src.configuration.domain.value_objects.serial_dispositivo import SerialDispositivo


@dataclass(eq=False)
class DispositivoIot:
    """Dispositivo IoT (sensor, cámara o gateway Edge) instalado en una infraestructura (RF-21).

    El serial es único. Un dispositivo puede colgar de un gateway Edge
    (``id_dispositivo_gateway``); las cámaras llevan además resolución, fps y
    cobertura.
    """
    serial: SerialDispositivo
    descripcion: str
    id_infraestructura: int
    id_tipo_dispositivo: int
    es_activo: bool
    fecha_creacion: datetime.datetime
    id_dispositivo_iot: Optional[int] = None
    # Gateway Edge que lo atiende (N:1). None: es un Edge o aún no tiene uno.
    id_dispositivo_gateway: Optional[int] = None
    # RF-21 v2.0 (RFC-011): solo cámaras; nulos para cualquier otra categoría.
    resolucion: Optional[str] = None
    fps: Optional[int] = None
    area_cobertura_m2: Optional[Decimal] = None
    # Derivada del tipo (SENSOR | CAMARA); no se persiste en el dispositivo.
    categoria: Optional[str] = None

    @classmethod
    def crear(
        cls,
        *,
        serial: SerialDispositivo,
        descripcion: str,
        id_infraestructura: int,
        id_tipo_dispositivo: int,
        es_activo: bool = True,
        id_dispositivo_gateway: Optional[int] = None,
        resolucion: Optional[str] = None,
        fps: Optional[int] = None,
        area_cobertura_m2: Optional[Decimal] = None,
    ) -> DispositivoIot:
        return cls(
            serial=serial,
            descripcion=descripcion,
            id_infraestructura=id_infraestructura,
            id_tipo_dispositivo=id_tipo_dispositivo,
            es_activo=es_activo,
            fecha_creacion=datetime.datetime.now(datetime.timezone.utc),
            id_dispositivo_gateway=id_dispositivo_gateway,
            resolucion=resolucion,
            fps=fps,
            area_cobertura_m2=area_cobertura_m2,
        )

    def desactivar(self) -> None:
        self.es_activo = False

    def asignar_gateway(self, id_dispositivo_gateway: Optional[int]) -> None:
        self.id_dispositivo_gateway = id_dispositivo_gateway

    def _snapshot(self) -> dict:
        return {
            "serial": self.serial.valor,
            "descripcion": self.descripcion,
            "id_infraestructura": self.id_infraestructura,
            "id_tipo_dispositivo": self.id_tipo_dispositivo,
            "es_activo": self.es_activo,
            "id_dispositivo_gateway": self.id_dispositivo_gateway,
            "resolucion": self.resolucion,
            "fps": self.fps,
            "area_cobertura_m2": str(self.area_cobertura_m2) if self.area_cobertura_m2 is not None else None,
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DispositivoIot):
            return NotImplemented
        if self.id_dispositivo_iot is None or other.id_dispositivo_iot is None:
            return self is other
        return self.id_dispositivo_iot == other.id_dispositivo_iot

    def __hash__(self) -> int:
        return hash(self.id_dispositivo_iot)

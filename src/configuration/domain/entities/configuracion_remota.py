"""Entidad de dominio ``ConfiguracionRemota`` — comando de configuración enviado a un dispositivo IoT (RF-23).

Estado: PENDIENTE (guardado, en vuelo o dispositivo offline) / APLICADA
(ACK confirmado) / NO_CONF (se publicó pero el ACK no llegó dentro del
timeout) / CANCELADA (no escrito por ningún código hoy).
Cada cambio de configuración crea un nuevo registro; la tabla es el historial.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Optional


@dataclass(eq=False)
class ConfiguracionRemota:
    id_dispositivo_iot: int
    frecuencia_captura: int
    intervalo_transmision: int
    estado: str
    id_usuario: int
    id_configuracion_remota: Optional[int] = None
    fecha_creacion: Optional[datetime.datetime] = None
    fecha_aplicacion: Optional[datetime.datetime] = None

    @classmethod
    def crear(
        cls,
        *,
        id_dispositivo_iot: int,
        frecuencia_captura: int,
        intervalo_transmision: int,
        id_usuario: int,
    ) -> ConfiguracionRemota:
        return cls(
            id_dispositivo_iot=id_dispositivo_iot,
            frecuencia_captura=frecuencia_captura,
            intervalo_transmision=intervalo_transmision,
            estado="PENDIENTE",
            id_usuario=id_usuario,
        )

    def marcar_aplicada(self, fecha: datetime.datetime) -> None:
        self.estado = "APLICADA"
        self.fecha_aplicacion = fecha

    def marcar_no_confirmada(self) -> None:
        self.estado = "NO_CONF"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ConfiguracionRemota):
            return NotImplemented
        if self.id_configuracion_remota is None or other.id_configuracion_remota is None:
            return self is other
        return self.id_configuracion_remota == other.id_configuracion_remota

    def __hash__(self) -> int:
        return hash(self.id_configuracion_remota)

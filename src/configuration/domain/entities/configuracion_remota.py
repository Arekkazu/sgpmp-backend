"""Entidad de dominio ``ConfiguracionRemota`` — comando de configuración enviado a un dispositivo IoT (RF-23).

Estado: PENDIENTE (guardado, en vuelo o dispositivo offline) / APLICADA
(ACK confirmado) / NO_CONF (se publicó pero el ACK no llegó dentro del
timeout) / CANCELADA (el usuario la descartó).
Cada cambio de configuración crea un nuevo registro; la tabla es el historial.
Solo PENDIENTE y NO_CONF se pueden reintentar o cancelar.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Optional


@dataclass(eq=False)
class ConfiguracionRemota:
    """Comando de configuración (frecuencia de captura e intervalo de transmisión) enviado a un dispositivo (RF-23).

    Ciclo de vida: PENDIENTE → APLICADA al llegar el ACK, NO_CONF si el ACK no
    llega a tiempo, o CANCELADA si el usuario la descarta.
    """
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

    def marcar_pendiente(self) -> None:
        self.estado = "PENDIENTE"

    def cancelar(self) -> None:
        self.estado = "CANCELADA"

    @property
    def sin_aplicar(self) -> bool:
        return self.estado in ("PENDIENTE", "NO_CONF")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ConfiguracionRemota):
            return NotImplemented
        if self.id_configuracion_remota is None or other.id_configuracion_remota is None:
            return self is other
        return self.id_configuracion_remota == other.id_configuracion_remota

    def __hash__(self) -> int:
        return hash(self.id_configuracion_remota)

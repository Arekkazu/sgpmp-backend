# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-25 | Arekkazu | INC-M03-134-G192 RF-62: cámara por id para su fps configurado |
# | 2026-10-29 | Arekkazu | INC-M03-134-G03 RF-60 CA-7/RF-53 E1: mantenimiento desde cualquier estado y lecturas rechazadas |
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from src.telemetry.domain.entities.telemetria import DispositivoInfo


@dataclass
class CamaraInfo:
    id_dispositivo_iot: int
    id_infraestructura: int
    es_activo: bool
    es_camara: bool
    fps_nominal: Optional[int]


@dataclass
class DispositivoHeartbeatInfo:
    id_dispositivo_iot: int
    id_infraestructura: int
    es_activo: bool
    en_mantenimiento: bool = False


class DispositivoPort(ABC):

    def obtener_camara_por_serial(self, serial: str) -> Optional[CamaraInfo]:
        """Identidad D4 tras autenticar al broker; el serial no es una credencial."""
        raise NotImplementedError

    def obtener_camara_por_id(self, id_dispositivo_iot: int) -> Optional[CamaraInfo]:
        """Cámara ya registrada (RF-62 la necesita por su fps configurado en RF-23)."""
        raise NotImplementedError

    @abstractmethod
    def obtener_dispositivo_activo(
        self,
        device_id: int,
        sensor_id: int,
        serial: str,
    ) -> Optional[DispositivoInfo]:
        """Resuelve el dispositivo y el sensor contra M09.

        El serial no es una credencial (D3, AIOT-DEV-03): el broker ya autenticó
        al nodo por MQTT y lo envía como su identidad. Exigir que device_id y
        sensor_id pertenezcan a ese serial impide que un nodo reporte por otro.

        Retorna DispositivoInfo si device_id existe en modulo9.dispositivos_iot con
        ese serial y sensor_id pertenece a él; None en otro caso. El estado activo
        de cada uno lo decide quien llama.
        """

    @abstractmethod
    def validar_dispositivo_heartbeat(
        self,
        device_id: int,
        serial: str,
    ) -> Optional[DispositivoHeartbeatInfo]:
        """Resuelve el dispositivo de un heartbeat (sin sensor específico).

        Retorna None si device_id no existe o no corresponde al serial.
        """

    @abstractmethod
    def obtener_por_serial(self, serial: str) -> Optional[DispositivoHeartbeatInfo]:
        """Resuelve el dispositivo por su serial, para los eventos que el broker
        reenvía sin device_id (EVENTO_BUFFER, D10). None si no existe."""

    @abstractmethod
    def obtener_camara(self, device_id: int, serial: str) -> Optional[CamaraInfo]:
        """Identidad de una cámara de visión (RF-21 v2.0): device_id + serial, sin sensor.

        Retorna None si el dispositivo no existe o no corresponde al serial.
        """

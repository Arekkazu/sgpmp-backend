# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-28 RF-60: etapa de diagnostico de ventanas de vision |
"""Progreso durable por responsabilidad, independiente del canal de entrada."""
from enum import Enum
from typing import Protocol


class EtapaPostcommit(str, Enum):
    RF61 = 'RF61'
    RF62 = 'RF62'
    RF17 = 'RF17'
    VISION_DETECCION = 'VISION_DETECCION'
    HEARTBEAT_ESTADO = 'HEARTBEAT_ESTADO'
    HEARTBEAT_ALERTAS = 'HEARTBEAT_ALERTAS'
    HEARTBEAT_SENSORES = 'HEARTBEAT_SENSORES'
    HEARTBEAT_TEMPERATURA = 'HEARTBEAT_TEMPERATURA'
    HEARTBEAT_FIRMWARE = 'HEARTBEAT_FIRMWARE'

    @property
    def es_heartbeat(self):
        return self.value.startswith('HEARTBEAT_')

    @property
    def es_vision(self):
        return self is EtapaPostcommit.VISION_DETECCION

    @property
    def requisito(self):
        if self is EtapaPostcommit.RF17:
            return EtapaPostcommit.RF61
        if self.es_heartbeat and self is not EtapaPostcommit.HEARTBEAT_ESTADO:
            return EtapaPostcommit.HEARTBEAT_ESTADO
        return None


class UnidadPostcommit(Protocol):
    db: object

    def pendientes(self, etapa: EtapaPostcommit, limite: int, reintento_seg: int) -> list[int]: ...
    def reclamar(self, etapa: EtapaPostcommit, identificador: int) -> bool: ...
    def registrar(self, etapa: EtapaPostcommit, identificador: int, error: str | None = None) -> None: ...
    def confirmar(self) -> None: ...

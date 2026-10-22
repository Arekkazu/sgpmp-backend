# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-41 RF-53/57: etapa de alertas tras RF-17/62    |
"""Progreso durable por responsabilidad, independiente del canal de entrada."""
from enum import Enum
from typing import Protocol


class EtapaPostcommit(str, Enum):
    RF61 = 'RF61'
    RF62 = 'RF62'
    RF17 = 'RF17'
    RF57 = 'RF57'
    HEARTBEAT_ESTADO = 'HEARTBEAT_ESTADO'
    HEARTBEAT_ALERTAS = 'HEARTBEAT_ALERTAS'
    HEARTBEAT_SENSORES = 'HEARTBEAT_SENSORES'
    HEARTBEAT_TEMPERATURA = 'HEARTBEAT_TEMPERATURA'
    HEARTBEAT_FIRMWARE = 'HEARTBEAT_FIRMWARE'

    @property
    def es_heartbeat(self):
        return self.value.startswith('HEARTBEAT_')

    @property
    def requisito(self):
        if self is EtapaPostcommit.RF57:
            return EtapaPostcommit.RF17
        if self is EtapaPostcommit.RF17:
            return EtapaPostcommit.RF61
        if self.es_heartbeat and self is not EtapaPostcommit.HEARTBEAT_ESTADO:
            return EtapaPostcommit.HEARTBEAT_ESTADO
        return None

    @property
    def requisitos(self):
        if self is EtapaPostcommit.RF57:
            return (EtapaPostcommit.RF17, EtapaPostcommit.RF62)
        return (self.requisito,) if self.requisito else ()


class UnidadPostcommit(Protocol):
    db: object

    def pendientes(self, etapa: EtapaPostcommit, limite: int, reintento_seg: int) -> list[int]: ...
    def reclamar(self, etapa: EtapaPostcommit, identificador: int) -> bool: ...
    def registrar(self, etapa: EtapaPostcommit, identificador: int, error: str | None = None, *, detalle: dict | None = None) -> None: ...
    def confirmar(self) -> None: ...

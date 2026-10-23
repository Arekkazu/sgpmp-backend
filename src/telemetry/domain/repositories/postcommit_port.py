# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-44 RF-61: separa progreso de vinculo y avisos requeridos |
# | 2026-10-22 | Leandro | DEV-47 RF-63: agrega progreso independiente para auditoria de fuentes |
"""Progreso durable por responsabilidad, independiente del canal de entrada."""
from enum import Enum
from typing import Protocol


class EtapaPostcommit(str, Enum):
    RF53_LECTURAS = 'RF53_LECTURAS'
    RF53_AUDITORIA = 'RF53_AUDITORIA'
    RF60_TRANSICIONES = 'RF60_TRANSICIONES'
    HEARTBEAT_AUDITORIA = 'HEARTBEAT_AUDITORIA'
    RF61 = 'RF61'
    RF61_AVISOS = 'RF61_AVISOS'
    RF62 = 'RF62'
    RF17 = 'RF17'
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
        if self in (EtapaPostcommit.RF17,EtapaPostcommit.RF61_AVISOS):
            return EtapaPostcommit.RF61
        if self is EtapaPostcommit.HEARTBEAT_AUDITORIA:
            return None
        if self.es_heartbeat and self is not EtapaPostcommit.HEARTBEAT_ESTADO:
            return EtapaPostcommit.HEARTBEAT_ESTADO
        return None


class UnidadPostcommit(Protocol):
    db: object

    def pendientes(self, etapa: EtapaPostcommit, limite: int, reintento_seg: int) -> list[int]: ...
    def reclamar(self, etapa: EtapaPostcommit, identificador: int) -> bool: ...
    def registrar(self, etapa: EtapaPostcommit, identificador: int, error: str | None = None) -> None: ...
    def confirmar(self) -> None: ...

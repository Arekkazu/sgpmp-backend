# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-26 | Leandro | INC-M03-125-G12 RF-53/63: definir respaldo de evidencia y destino idempotente sin acoplar el dominio a almacenamiento. |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, puertos y métodos |
"""Puertos de respaldo de la auditoría IoT (RF-53/RF-63).

``RespaldoAuditoriaIotPort`` guarda evidencia localmente cuando la persistencia
principal falla; ``DestinoRespaldoAuditoriaIotPort`` representa el destino
idempotente al que se sincroniza esa evidencia. El dominio no conoce el
almacenamiento concreto.
"""
from typing import Protocol
from uuid import UUID
from src.telemetry.domain.entities.evento_auditoria_iot import EventoAuditoriaIot


class RespaldoAuditoriaIotPort(Protocol):
    """Contrato del almacén local de eventos de auditoría pendientes de sincronizar."""

    def guardar(self, evento: EventoAuditoriaIot) -> None:
        """Guarda un evento en el respaldo local."""
        ...

    def listar(self, limite: int) -> list[EventoAuditoriaIot]:
        """Devuelve hasta ``limite`` eventos pendientes de sincronizar."""
        ...

    def confirmar(self, identificadores: list[UUID]) -> None:
        """Marca como sincronizados los eventos indicados."""
        ...

    def hay_pendientes(self) -> bool:
        """Indica si quedan eventos pendientes en el respaldo."""
        ...


class DestinoRespaldoAuditoriaIotPort(Protocol):
    """Contrato del destino remoto idempotente de los eventos respaldados."""

    def bloquear_respaldo(self) -> bool:
        """Intenta tomar el bloqueo de sincronización; evita ejecuciones simultáneas."""
        ...

    def registrar_respaldo(self, evento: EventoAuditoriaIot) -> None:
        """Registra el evento en el destino de forma idempotente."""
        ...

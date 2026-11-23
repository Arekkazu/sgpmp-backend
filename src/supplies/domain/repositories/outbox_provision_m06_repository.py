# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-79: outbox persistente hacia M06       |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto del outbox de provisiones hacia M06 (RF-79).

El evento se escribe en la misma transacción del movimiento que lo origina
(``encolar`` solo hace ``flush``), así un movimiento confirmado siempre deja su
evento y uno revertido no deja ninguno.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal

from src.supplies.domain.entities.evento_provision_m06 import EventoProvisionM06


class OutboxProvisionM06Repository(ABC):
    """Puerto de la bandeja de salida de provisiones hacia el módulo financiero."""
    @abstractmethod
    def encolar(self, evento: EventoProvisionM06) -> EventoProvisionM06:
        """Encola la provisión para su entrega."""
        raise NotImplementedError

    @abstractmethod
    def listar_listos(self, ahora: datetime, limite: int) -> list[EventoProvisionM06]:
        """Eventos no entregados cuyo próximo intento ya venció, en orden de creación."""
        raise NotImplementedError

    @abstractmethod
    def actualizar(self, evento: EventoProvisionM06) -> None:
        """Persiste estado, intentos y fechas del evento."""
        raise NotImplementedError

    @abstractmethod
    def contar_pendientes(self) -> int:
        """Eventos de cualquier ciclo aún sin entregar (RF-79 E7 e)."""
        raise NotImplementedError

    @abstractmethod
    def contar_sin_entregar(self, id_gestion_fases: int) -> int:
        """Eventos INCREMENTAL del ciclo retenidos en el outbox tras algún fallo de entrega (RF-79 E7 f)."""
        raise NotImplementedError

    @abstractmethod
    def sumar_incrementales(self, id_gestion_fases: int) -> Decimal:
        """Σ ``costo_registro`` de los eventos INCREMENTAL emitidos para el ciclo (RF-79 R11)."""
        raise NotImplementedError

# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-79: entrega de provisiones a M06       |
"""Puerto de entrega de provisiones de costos a M06 (RF-79).

``entregar`` devuelve normalmente cuando M06 confirmó la recepción (ACK de
recepción, R9) — también si M06 ya lo tenía (idempotencia por
``id_evento_provision``, R10). Cualquier excepción es un fallo de entrega y el
evento se reintenta.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.supplies.domain.entities.evento_provision_m06 import EventoProvisionM06


class ProvisionM06Port(ABC):
    @abstractmethod
    def entregar(self, evento: EventoProvisionM06) -> None:
        raise NotImplementedError

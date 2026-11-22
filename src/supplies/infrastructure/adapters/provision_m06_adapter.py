# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-79: entrega a M06 (in-process)         |
"""Adaptador de :class:`ProvisionM06Port` hacia el M06 provisional (``src/financial_valuation``).

M06 vive en el mismo backend y la misma BD: la entrega es una llamada a su caso
de uso de recepción en una sesión propia, así M06 confirma (ACK) con su propio
``commit``, independiente de la transacción de M05. TLS y token de servicio de
RF-79 R5 no aplican a una llamada en proceso; aplicarán cuando M06 sea un
servicio aparte y este adaptador se reemplace por un cliente HTTP/cola.
"""
from __future__ import annotations

from typing import Callable

from sqlalchemy.orm import Session

from src.financial_valuation.application.use_cases.provision_costos.recibir_provision_costos_use_case import (
    RecibirProvisionCostosUseCase,
)
from src.financial_valuation.domain.entities.recepcion_provision import RecepcionProvision
from src.financial_valuation.infrastructure.repositories.recepcion_provision_repository import (
    SqlAlchemyRecepcionProvisionRepository,
)
from src.supplies.domain.entities.evento_provision_m06 import EventoProvisionM06
from src.supplies.domain.repositories.provision_m06_port import ProvisionM06Port


class ProvisionM06Adapter(ProvisionM06Port):
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def entregar(self, evento: EventoProvisionM06) -> None:
        db = self.session_factory()
        try:
            RecibirProvisionCostosUseCase(db, SqlAlchemyRecepcionProvisionRepository(db)).execute(
                RecepcionProvision(
                    id_evento_provision=evento.id_evento_provision,
                    modalidad=evento.modalidad,
                    schema_version=evento.schema_version,
                    id_activo_biologico=evento.id_activo_biologico,
                    id_gestion_fases=evento.id_gestion_fases,
                    contenido=evento.contenido,
                )
            )
        finally:
            db.close()

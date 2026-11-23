# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-79: M06 provisional (recepción)        |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Caso de uso de M06: recibir una provisión de costos de M05 (RF-79 Fase 1 c / Fase 3).

El ACK es de recepción, no de procesamiento (R9). Un evento repetido (mismo
``id_evento_provision``) se ignora y se confirma igual (R10, CA-10).
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.financial_valuation.domain.entities.recepcion_provision import RecepcionProvision
from src.financial_valuation.domain.repositories.recepcion_provision_repository import (
    RecepcionProvisionRepository,
)


@dataclass(frozen=True)
class AckRecepcion:
    """Acuse de recibo de una provisión de costos."""
    recibido: bool
    duplicado: bool


class RecibirProvisionCostosUseCase:
    """Recibe las provisiones de costos enviadas por suministros."""
    def __init__(self, db: Session, repo: RecepcionProvisionRepository) -> None:
        self.db = db
        self.repo = repo

    def execute(self, recepcion: RecepcionProvision) -> AckRecepcion:
        """Registra la provisión si es nueva y devuelve el acuse."""
        try:
            nueva = self.repo.registrar_si_nueva(recepcion)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return AckRecepcion(recibido=True, duplicado=not nueva)

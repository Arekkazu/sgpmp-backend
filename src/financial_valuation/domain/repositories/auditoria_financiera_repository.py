# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..94: puerto del módulo financiero |
"""Puerto de la auditoría inmutable de M06 (RF-94)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria


class AuditoriaFinancieraRepository(ABC):
    @abstractmethod
    def registrar(self, evento: EventoAuditoria) -> None: ...

    @abstractmethod
    def consultar(self, filtros: dict, pagina: int, tamano: int) -> tuple[int, list[dict]]: ...

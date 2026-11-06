# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..94: puerto del módulo financiero |
# | 2026-11-05 | Arekkazu | M06 RF-94: orden descendente y conteo por severidad |
"""Puerto de la auditoría inmutable de M06 (RF-94)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria


class AuditoriaFinancieraRepository(ABC):
    @abstractmethod
    def registrar(self, evento: EventoAuditoria) -> None: ...

    @abstractmethod
    def consultar(self, filtros: dict, pagina: int, tamano: int, descendente: bool = False) -> tuple[int, list[dict]]: ...

    @abstractmethod
    def conteo_por_severidad(self, filtros: dict) -> dict[str, int]: ...

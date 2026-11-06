# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-98/RF-AE02: puerto de contratos y anexos |
"""Puerto de las versiones del contrato AAEF y de los anexos de mapeo."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.accounting_integration.domain.entities.contrato import AnexoMapeo, VersionContrato


class ContratoRepository(ABC):
    @abstractmethod
    def listar_contratos(self, bloquear: bool = False) -> list[VersionContrato]:
        """Todas las versiones. ``bloquear`` las toma ``FOR UPDATE`` (transiciones concurrentes, RF-98 CA-30)."""

    @abstractmethod
    def guardar_contrato(self, contrato: VersionContrato) -> VersionContrato: ...

    @abstractmethod
    def obtener_anexo(self, id_mapeo_anexo_aaef: int) -> Optional[AnexoMapeo]: ...

    @abstractmethod
    def listar_anexos(self) -> list[AnexoMapeo]: ...

    @abstractmethod
    def guardar_anexo(self, anexo: AnexoMapeo) -> AnexoMapeo: ...

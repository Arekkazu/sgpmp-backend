# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-98/RF-AE02: puerto de contratos y anexos |
# | 2026-11-19 | LuisfNarvaez01 | INC-M07-375 RF-98: guardar los datos de una versión pendiente modificada |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de las versiones del contrato AAEF y de los anexos de mapeo."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.accounting_integration.domain.entities.contrato import AnexoMapeo, VersionContrato


class ContratoRepository(ABC):
    """Puerto de persistencia de versiones del contrato y anexos."""
    @abstractmethod
    def listar_contratos(self, bloquear: bool = False) -> list[VersionContrato]:
        """Todas las versiones. ``bloquear`` las toma ``FOR UPDATE`` (transiciones concurrentes, RF-98 CA-30)."""

    @abstractmethod
    def guardar_contrato(self, contrato: VersionContrato) -> VersionContrato:
        """Guarda la versión del contrato."""
        ...

    @abstractmethod
    def guardar_datos_contrato(self, contrato: VersionContrato) -> VersionContrato:
        """Datos editables de una versión PENDIENTE (RF-98 5.12); el estado y sus fechas no se tocan aquí."""

    @abstractmethod
    def obtener_anexo(self, id_mapeo_anexo_aaef: int) -> Optional[AnexoMapeo]:
        """Devuelve el anexo por id, o ``None``."""
        ...

    @abstractmethod
    def listar_anexos(self) -> list[AnexoMapeo]:
        """Lista los anexos de mapeo."""
        ...

    @abstractmethod
    def guardar_anexo(self, anexo: AnexoMapeo) -> AnexoMapeo:
        """Guarda el anexo."""
        ...

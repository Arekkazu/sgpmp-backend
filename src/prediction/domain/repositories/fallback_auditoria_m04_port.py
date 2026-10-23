# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | DEV-37 RF-73 E2/E8: puerto del respaldo local de la auditoría de M04 |
"""Respaldo local de solo escritura de la auditoría de M04 (RF-73 E2 y E8).

Cuando el repositorio central no acepta un evento tras los reintentos, el evento se
guarda aquí con su ``id_evento`` y su ``fecha_evento`` originales. Al recuperarse la
BD se sincroniza en orden FIFO con ``origen_registro = FALLBACK``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class LoteFallback:
    """Un archivo del respaldo con sus eventos en el orden en que se escribieron."""
    identificador: str
    eventos: list[dict]


class FallbackAuditoriaM04Port(ABC):
    @abstractmethod
    def escribir(self, evento: dict) -> None:
        """Agrega el evento al respaldo. Nunca propaga: el respaldo es el último recurso."""

    @abstractmethod
    def pendientes(self) -> list[LoteFallback]:
        """Lotes sin sincronizar, del más antiguo al más nuevo."""

    @abstractmethod
    def marcar_sincronizado(self, identificador: str) -> None:
        """El lote ya está en el repositorio central; no se vuelve a leer."""

# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-102: puerto de la auditoría de integración |
"""Puerto de la auditoría de M07 (RF-102): solo inserta y consulta, nunca modifica."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Optional

from src.accounting_integration.domain.entities.evento_integracion import EventoIntegracion


@dataclass(frozen=True)
class FiltrosAuditoria:
    tipos_evento: Optional[tuple[str, ...]] = None
    id_cliente_externo: Optional[int] = None
    desde: Optional[date] = None
    hasta: Optional[date] = None
    endpoint: Optional[str] = None
    codigo_http: Optional[int] = None
    solo_exitosos: bool = False


class AuditoriaIntegracionRepository(ABC):
    @abstractmethod
    def registrar(self, evento: EventoIntegracion) -> None:
        """Inserta el evento con su hash, en la transacción de la sesión (sin ``commit``)."""

    @abstractmethod
    def consultar(self, filtros: FiltrosAuditoria, pagina: int, tamano: int) -> tuple[list[tuple[EventoIntegracion, str, dict]], int]:
        """Eventos filtrados con el hash guardado (para verificar integridad), los datos legibles de
        quién actuó (``correo_usuario``, ``nombre_cliente``) y el total."""

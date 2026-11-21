# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-102: puerto de la auditoría de integración |
# | 2026-11-14 | Arekkazu | FILTRO-FINCA RF-98: la auditoría de la integración se filtra por el titular (NIT) de una finca del usuario |
# | 2026-11-20 | Arekkazu | QA-M07 CU07 H-01/S-02 RF-102: días del filtro en la zona del usuario y filtro por versión |
"""Puerto de la auditoría de M07 (RF-102): solo inserta y consulta, nunca modifica."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Optional

from src.accounting_integration.domain.entities.evento_integracion import EventoIntegracion


@dataclass(frozen=True)
class FiltrosAuditoria:
    """``desde`` y ``hasta`` son días calendario del usuario (su zona horaria), ambos incluidos."""
    tipos_evento: Optional[tuple[str, ...]] = None
    id_cliente_externo: Optional[int] = None
    desde: Optional[date] = None
    hasta: Optional[date] = None
    endpoint: Optional[str] = None
    codigo_http: Optional[int] = None
    solo_exitosos: bool = False
    numero_id_tributaria: Optional[str] = None
    version_contrato: Optional[str] = None


class AuditoriaIntegracionRepository(ABC):
    @abstractmethod
    def registrar(self, evento: EventoIntegracion) -> None:
        """Inserta el evento con su hash, en la transacción de la sesión (sin ``commit``)."""

    @abstractmethod
    def consultar(self, filtros: FiltrosAuditoria, pagina: int, tamano: int) -> tuple[list[tuple[EventoIntegracion, str, dict]], int]:
        """Eventos filtrados con el hash guardado (para verificar integridad), los datos legibles de
        quién actuó (``correo_usuario``, ``nombre_cliente``) y el total."""

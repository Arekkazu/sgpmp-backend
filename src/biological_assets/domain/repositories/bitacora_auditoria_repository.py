from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.biological_assets.domain.entities.activo_biologico import EventoAuditoria


class BitacoraAuditoriaRepository(ABC):

    @abstractmethod
    def registrar(self, evento: EventoAuditoria) -> None:
        """Calcula hash_integridad, inserta en bitacora_auditoria_m02 y hace flush().
        Lanza excepción si falla; el caller es responsable de ignorarla si aplica."""

    @abstractmethod
    def consultar(
        self,
        rf_origen: Optional[str],
        tipo_evento: Optional[str],
        id_activo_biologico: Optional[int],
        clasificacion_biologica: Optional[str],
        resultado: Optional[str],
        severidad_log: Optional[str],
        fecha_inicio: Optional[datetime],
        fecha_fin: Optional[datetime],
        pagina: int,
        page_size: int,
    ) -> tuple[list[EventoAuditoria], int]:
        """Retorna (registros, total_count) aplicando filtros y paginación."""

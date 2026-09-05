from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.biological_assets.domain.entities.activo_biologico import HistoricoEstado


class HistoricoEstadoRepository(ABC):
    @abstractmethod
    def registrar(
        self,
        id_activo: int,
        id_estado_anterior: int,
        id_estado_nuevo: int,
        fecha: datetime,
        motivo: Optional[str],
        usuario_id: int,
        modulo_origen: str,
    ) -> HistoricoEstado:
        """Inserta un registro inmutable de cambio de estado y retorna la entidad."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.prediction.domain.entities.historial_diagnostico import EventoHistorial


class HistorialDiagnosticoRepository(ABC):
    @abstractmethod
    def consultar(
        self,
        *,
        id_activo_biologico: int,
        fecha_inicio: datetime,
        fecha_fin: datetime,
        nivel_riesgo: Optional[int],
        id_patologia: Optional[int],
        incluir_alertas: bool,
        cursor: Optional[tuple[datetime, str]],
        limite: int,
    ) -> list[dict]: ...

    @abstractmethod
    def materializar_eventos(self, eventos: list[EventoHistorial]) -> None: ...

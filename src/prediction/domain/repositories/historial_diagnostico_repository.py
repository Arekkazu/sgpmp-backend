# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-25 | Arekkazu | INC-M04-143/144/146 RF-67: eventos ordenados, id estable y nombre histórico |
from __future__ import annotations

import uuid
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
        cursor: Optional[tuple[datetime, uuid.UUID]],
        limite: int,
    ) -> list[EventoHistorial]:
        """Hasta ``limite`` eventos (inferencias, alertas y retroalimentaciones)
        ordenados por (fecha_evento, id_evento) DESC y anteriores al cursor.

        ``id_evento`` es estable: el mismo evento tiene el mismo id en cada
        consulta. ``nombre_patologia`` es el vigente a la fecha del evento.
        """

    @abstractmethod
    def materializar_eventos(self, eventos: list[EventoHistorial]) -> None:
        """Guarda los eventos que faltan; consultas simultáneas no los duplican."""

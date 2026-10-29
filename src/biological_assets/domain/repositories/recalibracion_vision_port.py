"""Puerto hacia M09 para el disparo automático de la calibración por visión (RF-24 v2.0, #551)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class RecalibracionVisionPort(ABC):
    """Avisa a M09 que un área tuvo un nuevo lote o un fin de ciclo."""

    @abstractmethod
    def solicitar(self, id_infraestructura: int, momento: datetime, motivo: str) -> None:
        """Pide recalcular la línea base por visión del área.

        No falla ni bloquea la operación de M02: el resultado (exitoso, fallido
        o no aplica) queda en el historial de calibraciones y en RF-10.
        """

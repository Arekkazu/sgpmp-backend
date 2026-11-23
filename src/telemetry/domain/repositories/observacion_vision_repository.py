# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-25 | Arekkazu | INC-M03-134-G192 RF-62: obtener y guardar la evaluación de calidad |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de persistencia de observaciones de visión."""
from __future__ import annotations

import datetime
from abc import ABC, abstractmethod

from src.telemetry.domain.entities.observacion_vision import ObservacionVision


class ObservacionVisionRepository(ABC):
    """Puerto para guardar observaciones de visión y detectar duplicados."""

    @abstractmethod
    def fechas_existentes(
        self, id_dispositivo_iot: int, fechas: list[datetime.datetime]
    ) -> set[datetime.datetime]:
        """De ``fechas``, las que ya tienen observación de esa cámara (reenvío del buffer)."""

    @abstractmethod
    def guardar(self, observacion: ObservacionVision) -> ObservacionVision | None:
        """None si ya existe la clave cámara/fecha, incluso ante concurrencia."""

    @abstractmethod
    def obtener(self, id_observacion_vision: int) -> ObservacionVision | None:
        """La observación, bloqueada para evaluarla sin carreras entre el worker y el endpoint."""

    @abstractmethod
    def guardar_evaluacion(self, observacion: ObservacionVision) -> None:
        """Persiste solo el bloque de calidad de RF-62; los indicadores no cambian."""

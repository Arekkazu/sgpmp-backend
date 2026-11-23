# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Frontera con la función de ingesta común a HTTP y al broker (B+)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ResultadoPersistenciaIngesta:
    """Resultado de la función SQL de ingesta."""
    id_telemetria: int | None
    estado_calidad: str | None
    mensaje: str
    timestamp_procesamiento: datetime | None = None
    latencia_procesamiento_ms: int | None = None


class IngestaTelemetriaPort(ABC):
    """Puerto que ejecuta la ingesta de telemetría en la base."""
    @abstractmethod
    def ingerir(self, parametros: dict[str, Any]) -> ResultadoPersistenciaIngesta:
        """Ejecuta la función SQL sin confirmar ni revertir la transacción."""

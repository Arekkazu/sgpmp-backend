"""Frontera con la función de ingesta común a HTTP y al broker (B+)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ResultadoPersistenciaIngesta:
    id_telemetria: int | None
    estado_calidad: str | None
    mensaje: str
    timestamp_procesamiento: datetime | None = None
    latencia_procesamiento_ms: int | None = None


class IngestaTelemetriaPort(ABC):
    @abstractmethod
    def ingerir(self, parametros: dict[str, Any]) -> ResultadoPersistenciaIngesta:
        """Ejecuta la función SQL sin confirmar ni revertir la transacción."""

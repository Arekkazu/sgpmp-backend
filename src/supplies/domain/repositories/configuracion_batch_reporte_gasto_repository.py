"""Puerto de lectura de la configuración del motor async de reportes de gastos (RF-77)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ConfiguracionBatchReporteGasto:
    """Parámetros del motor async (fila única de ``configuracion_batch_reportes_gastos``)."""

    num_workers_max: int
    max_reintentos: int
    backoff_minutos: list[int]
    limite_concurrencia: int
    intervalo_poll_segundos: int
    es_activo: bool


class ConfiguracionBatchReporteGastoRepository(ABC):
    @abstractmethod
    def obtener(self) -> ConfiguracionBatchReporteGasto:
        raise NotImplementedError

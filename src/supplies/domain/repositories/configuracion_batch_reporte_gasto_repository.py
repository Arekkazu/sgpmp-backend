# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
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
    """Puerto de la configuración del procesamiento asíncrono de reportes de gastos."""
    @abstractmethod
    def obtener(self) -> ConfiguracionBatchReporteGasto:
        """Devuelve la configuración vigente."""
        raise NotImplementedError

"""Puerto de lectura de la configuración del motor async de historial de suministros (RF-81)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ConfiguracionBatchHistorial:
    """Parámetros del motor async (fila única de ``configuracion_batch_historial_suministros``)."""

    num_workers_max: int
    max_reintentos: int
    backoff_minutos: list[int]
    limite_concurrencia_exportaciones: int
    limite_concurrencia_consultas: int
    umbral_nivel3: int
    umbral_nivel4: int
    tope_maximo_registros: int
    umbral_exportacion_async: int
    intervalo_poll_segundos: int
    es_activo: bool


class ConfiguracionBatchHistorialRepository(ABC):
    @abstractmethod
    def obtener(self) -> ConfiguracionBatchHistorial:
        raise NotImplementedError

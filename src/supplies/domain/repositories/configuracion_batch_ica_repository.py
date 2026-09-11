"""Puerto de lectura de la configuración del motor batch ICA (RF-74)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import time


@dataclass(frozen=True)
class ConfiguracionBatch:
    """Parámetros del motor batch (fila única de ``configuracion_batch_ica``)."""

    limite_activos: int
    num_workers_max: int
    umbral_paralelizacion: int
    ventana_horas: int
    hora_ejecucion: time
    max_reintentos: int
    backoff_minutos: list[int]
    es_activo: bool


class ConfiguracionBatchICARepository(ABC):
    @abstractmethod
    def obtener(self) -> ConfiguracionBatch:
        """Devuelve la configuración vigente del motor batch (fila única)."""
        raise NotImplementedError

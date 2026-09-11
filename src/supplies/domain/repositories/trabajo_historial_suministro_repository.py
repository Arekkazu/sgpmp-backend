"""Puerto de la cola de trabajos pesados de historial de suministros (RF-81)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.supplies.domain.entities.trabajo_historial_suministro import (
    EjecucionHistorialSuministro,
    TrabajoHistorialSuministro,
)
from src.supplies.domain.value_objects.estado_trabajo_async import EstadoTrabajoAsync


class TrabajoHistorialSuministroRepository(ABC):
    @abstractmethod
    def encolar(self, trabajo: TrabajoHistorialSuministro) -> TrabajoHistorialSuministro:
        raise NotImplementedError

    @abstractmethod
    def contar_activos(self, tipo_trabajo: str) -> int:
        """Trabajos en PENDIENTE + EN_PROCESO del tipo dado (control de concurrencia 429)."""
        raise NotImplementedError

    @abstractmethod
    def obtener(self, id_cola: int) -> Optional[TrabajoHistorialSuministro]:
        raise NotImplementedError

    @abstractmethod
    def listar_pendientes(self, limite: int) -> list[TrabajoHistorialSuministro]:
        raise NotImplementedError

    @abstractmethod
    def marcar_estado(
        self, id_cola: int, estado: EstadoTrabajoAsync, *, fecha_procesado: Optional[datetime] = None
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def crear_ejecucion(self, ejecucion: EjecucionHistorialSuministro) -> EjecucionHistorialSuministro:
        raise NotImplementedError

    @abstractmethod
    def guardar_ejecucion(self, ejecucion: EjecucionHistorialSuministro) -> EjecucionHistorialSuministro:
        raise NotImplementedError

    @abstractmethod
    def obtener_ultima_ejecucion(self, id_cola: int) -> Optional[EjecucionHistorialSuministro]:
        raise NotImplementedError

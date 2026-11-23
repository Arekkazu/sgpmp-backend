# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-81 R8: límite por usuario              |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
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
    """Puerto de la cola de trabajos asíncronos del historial."""
    @abstractmethod
    def encolar(self, trabajo: TrabajoHistorialSuministro) -> TrabajoHistorialSuministro:
        """Encola el trabajo."""
        raise NotImplementedError

    @abstractmethod
    def contar_activos(self, tipo_trabajo: str, id_usuario: Optional[int] = None) -> int:
        """Trabajos en PENDIENTE + EN_PROCESO del tipo dado (control de concurrencia 429)."""
        raise NotImplementedError

    @abstractmethod
    def obtener(self, id_cola: int) -> Optional[TrabajoHistorialSuministro]:
        """Devuelve el trabajo, o ``None``."""
        raise NotImplementedError

    @abstractmethod
    def listar_pendientes(self, limite: int) -> list[TrabajoHistorialSuministro]:
        """Lista los trabajos pendientes."""
        raise NotImplementedError

    @abstractmethod
    def marcar_estado(
        self, id_cola: int, estado: EstadoTrabajoAsync, *, fecha_procesado: Optional[datetime] = None
    ) -> None:
        """Cambia el estado del trabajo."""
        raise NotImplementedError

    @abstractmethod
    def crear_ejecucion(self, ejecucion: EjecucionHistorialSuministro) -> EjecucionHistorialSuministro:
        """Registra una ejecución del trabajo."""
        raise NotImplementedError

    @abstractmethod
    def guardar_ejecucion(self, ejecucion: EjecucionHistorialSuministro) -> EjecucionHistorialSuministro:
        """Actualiza la ejecución."""
        raise NotImplementedError

    @abstractmethod
    def obtener_ultima_ejecucion(self, id_cola: int) -> Optional[EjecucionHistorialSuministro]:
        """Devuelve la última ejecución del trabajo, o ``None``."""
        raise NotImplementedError

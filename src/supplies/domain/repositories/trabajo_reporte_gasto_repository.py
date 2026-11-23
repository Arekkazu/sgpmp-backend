# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de la cola de trabajos de generación async de reportes de gastos (RF-77)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.supplies.domain.entities.trabajo_reporte_gasto import EjecucionReporteGasto, TrabajoReporteGasto
from src.supplies.domain.value_objects.estado_trabajo_async import EstadoTrabajoAsync


class TrabajoReporteGastoRepository(ABC):
    """Puerto de la cola de trabajos del reporte de gastos."""
    @abstractmethod
    def encolar(self, trabajo: TrabajoReporteGasto) -> TrabajoReporteGasto:
        """Encola el trabajo."""
        raise NotImplementedError

    @abstractmethod
    def contar_activos(self) -> int:
        """Trabajos en PENDIENTE + EN_PROCESO (para el control de concurrencia 429)."""
        raise NotImplementedError

    @abstractmethod
    def obtener(self, id_cola: int) -> Optional[TrabajoReporteGasto]:
        """Devuelve el trabajo, o ``None``."""
        raise NotImplementedError

    @abstractmethod
    def listar_pendientes(self, limite: int) -> list[TrabajoReporteGasto]:
        """Lista los trabajos pendientes."""
        raise NotImplementedError

    @abstractmethod
    def marcar_estado(
        self, id_cola: int, estado: EstadoTrabajoAsync, *, fecha_procesado: Optional[datetime] = None
    ) -> None:
        """Cambia el estado del trabajo."""
        raise NotImplementedError

    @abstractmethod
    def crear_ejecucion(self, ejecucion: EjecucionReporteGasto) -> EjecucionReporteGasto:
        """Registra una ejecución del trabajo."""
        raise NotImplementedError

    @abstractmethod
    def guardar_ejecucion(self, ejecucion: EjecucionReporteGasto) -> EjecucionReporteGasto:
        """Actualiza la ejecución."""
        raise NotImplementedError

    @abstractmethod
    def obtener_ultima_ejecucion(self, id_cola: int) -> Optional[EjecucionReporteGasto]:
        """Devuelve la última ejecución del trabajo, o ``None``."""
        raise NotImplementedError

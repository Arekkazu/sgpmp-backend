"""Puertos de la exportación asíncrona de auditoría (RF-10)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.identity_access.domain.entities.exportacion_auditoria import (
    ConfiguracionExportacion,
    ResultadoExportacion,
    TrabajoExportacion,
)


class ExportacionAuditoriaRepository(ABC):
    """Persistencia de la cola de exportaciones y sus resultados."""

    @abstractmethod
    def encolar(self, trabajo: TrabajoExportacion) -> TrabajoExportacion:
        """Registra la solicitud en estado ``PENDIENTE``."""
        raise NotImplementedError

    @abstractmethod
    def obtener(self, id_cola: int) -> Optional[TrabajoExportacion]:
        """Devuelve el trabajo con su estado actual, o ``None`` si no existe."""
        raise NotImplementedError

    @abstractmethod
    def contar_activos(self) -> int:
        """Trabajos en ``PENDIENTE`` o ``EN_PROCESO`` (control de concurrencia, 429)."""
        raise NotImplementedError

    @abstractmethod
    def tomar_pendiente(self) -> Optional[TrabajoExportacion]:
        """Reclama el trabajo pendiente más antiguo y lo marca ``EN_PROCESO``.

        Debe bloquear la fila (``FOR UPDATE SKIP LOCKED``) para que dos workers
        no procesen el mismo trabajo.
        """
        raise NotImplementedError

    @abstractmethod
    def completar(self, id_cola: int, resultado: ResultadoExportacion) -> None:
        """Guarda el CSV generado y pasa el trabajo a ``COMPLETADO``."""
        raise NotImplementedError

    @abstractmethod
    def fallar(self, id_cola: int, error: str, reintentable: bool) -> None:
        """Anota el error y devuelve el trabajo a la cola o lo marca ``FALLIDO``."""
        raise NotImplementedError

    @abstractmethod
    def obtener_resultado(self, id_cola: int) -> Optional[ResultadoExportacion]:
        """Devuelve el CSV de un trabajo completado."""
        raise NotImplementedError

    @abstractmethod
    def obtener_configuracion(self) -> ConfiguracionExportacion:
        """Lee la fila única de configuración; valores por defecto si falta."""
        raise NotImplementedError

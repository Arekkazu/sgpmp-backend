# | Fecha      | Nombre   | Que se hizo                                                  |
# |------------|----------|--------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-104: puertos de solicitudes, archivos, render y avisos |
"""Puertos de RF-104: persistencia de solicitudes y archivos, render a PDF/Excel y avisos (auditoría y
notificación). La aplicación solo conoce estos contratos."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from uuid import UUID

from src.reporting.domain.reportes.contenido import ContenidoReporte
from src.reporting.domain.reportes.solicitud import ArchivoReporte, SolicitudReporte


class SolicitudReporteRepository(ABC):

    @abstractmethod
    def guardar(self, solicitud: SolicitudReporte) -> SolicitudReporte:
        """Inserta (sin id) o actualiza la solicitud; devuelve la entidad con id y fechas de la BD."""

    @abstractmethod
    def guardar_archivos(self, id_solicitud: UUID, partes: list[ArchivoReporte]) -> None: ...

    @abstractmethod
    def obtener(self, id_solicitud: UUID, *, bloquear: bool = False) -> Optional[SolicitudReporte]:
        """La solicitud aunque sea de otro usuario (para responder 403 y no 404)."""

    @abstractmethod
    def obtener_archivo(self, id_solicitud: UUID, numero_parte: int) -> Optional[ArchivoReporte]: ...

    @abstractmethod
    def listar_archivos(self, id_solicitud: UUID) -> list[ArchivoReporte]:
        """Las partes sin su contenido (nombre, tamaño, checksum)."""

    @abstractmethod
    def listar_por_usuario(self, id_usuario: int, limite: int) -> list[SolicitudReporte]: ...

    @abstractmethod
    def tomar_pendientes(self, ahora: datetime, limite: int) -> list[SolicitudReporte]:
        """EN_PROCESO cuyo próximo intento ya llegó, bloqueadas para este proceso (``SKIP LOCKED``)."""

    @abstractmethod
    def tomar_vencidas(self, ahora: datetime, limite: int) -> list[SolicitudReporte]: ...

    @abstractmethod
    def borrar_contenido(self, id_solicitud: UUID) -> None:
        """Al vencer: borra el contenido de las partes y deja la fila como rastro."""


class RenderizadorReportePort(ABC):

    @abstractmethod
    def renderizar(self, contenido: ContenidoReporte, formato: str, ruta_logo: Optional[str]) -> bytes: ...

    @abstractmethod
    def tipo_contenido(self, formato: str) -> str: ...

    @abstractmethod
    def extension(self, formato: str) -> str: ...


class AvisosReportesPort(ABC):
    """Auditoría de cada generación (CA-15) y aviso al usuario de los reportes en segundo plano (CA-10)."""

    @abstractmethod
    def registrar(self, solicitud: SolicitudReporte, titulo: str, detalle: dict, notificar: bool) -> None:
        """Deja el evento de auditoría (generado o fallido) y, si ``notificar``, el aviso en la bandeja del usuario.
        Nunca propaga errores: un aviso perdido no deshace el reporte."""

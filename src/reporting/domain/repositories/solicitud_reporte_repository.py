# | Fecha      | Nombre   | Que se hizo                                                  |
# |------------|----------|--------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-104: puertos de solicitudes, archivos, render y avisos |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
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
    """Puerto de persistencia de solicitudes de reportes."""

    @abstractmethod
    def guardar(self, solicitud: SolicitudReporte) -> SolicitudReporte:
        """Inserta (sin id) o actualiza la solicitud; devuelve la entidad con id y fechas de la BD."""

    @abstractmethod
    def guardar_archivos(self, id_solicitud: UUID, partes: list[ArchivoReporte]) -> None:
        """Guarda las partes generadas del reporte."""
        ...

    @abstractmethod
    def obtener(self, id_solicitud: UUID, *, bloquear: bool = False) -> Optional[SolicitudReporte]:
        """La solicitud aunque sea de otro usuario (para responder 403 y no 404)."""

    @abstractmethod
    def obtener_archivo(self, id_solicitud: UUID, numero_parte: int) -> Optional[ArchivoReporte]:
        """Devuelve la parte del reporte, o ``None``."""
        ...

    @abstractmethod
    def listar_archivos(self, id_solicitud: UUID) -> list[ArchivoReporte]:
        """Las partes sin su contenido (nombre, tamaño, checksum)."""

    @abstractmethod
    def listar_por_usuario(self, id_usuario: int, limite: int) -> list[SolicitudReporte]:
        """Lista las solicitudes recientes del usuario."""
        ...

    @abstractmethod
    def tomar_pendientes(self, ahora: datetime, limite: int) -> list[SolicitudReporte]:
        """EN_PROCESO cuyo próximo intento ya llegó, bloqueadas para este proceso (``SKIP LOCKED``)."""

    @abstractmethod
    def tomar_vencidas(self, ahora: datetime, limite: int) -> list[SolicitudReporte]:
        """Toma las solicitudes vencidas para expirarlas."""
        ...

    @abstractmethod
    def borrar_contenido(self, id_solicitud: UUID) -> None:
        """Al vencer: borra el contenido de las partes y deja la fila como rastro."""


class RenderizadorReportePort(ABC):
    """Puerto que convierte el contenido de un reporte en archivo."""

    @abstractmethod
    def renderizar(self, contenido: ContenidoReporte, formato: str, ruta_logo: Optional[str]) -> bytes:
        """Genera el archivo del reporte en el formato indicado."""
        ...

    @abstractmethod
    def tipo_contenido(self, formato: str) -> str:
        """Tipo MIME del formato."""
        ...

    @abstractmethod
    def extension(self, formato: str) -> str:
        """Extensión de archivo del formato."""
        ...


class AvisosReportesPort(ABC):
    """Auditoría de cada generación (CA-15) y aviso al usuario de los reportes en segundo plano (CA-10)."""

    @abstractmethod
    def registrar(self, solicitud: SolicitudReporte, titulo: str, detalle: dict, notificar: bool) -> None:
        """Deja el evento de auditoría (generado o fallido) y, si ``notificar``, el aviso en la bandeja del usuario.
        Nunca propaga errores: un aviso perdido no deshace el reporte."""

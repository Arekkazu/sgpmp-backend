"""Entidades de dominio de la exportación asíncrona de auditoría (RF-10)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class EstadoExportacion(str, Enum):
    """Ciclo de vida de un trabajo de exportación."""

    PENDIENTE = "PENDIENTE"
    EN_PROCESO = "EN_PROCESO"
    COMPLETADO = "COMPLETADO"
    FALLIDO = "FALLIDO"


@dataclass
class TrabajoExportacion:
    """Solicitud de exportación encolada."""

    parametros: dict
    id_usuario_solicitante: int
    id_cola: Optional[int] = None
    estado: str = EstadoExportacion.PENDIENTE.value
    intentos: int = 0
    error: Optional[str] = None
    fecha_solicitud: Optional[datetime] = None
    fecha_procesado: Optional[datetime] = None
    # Solo viene poblado cuando el trabajo terminó bien.
    total_exportado: Optional[int] = None
    total_disponible: Optional[int] = None

    @property
    def descargable(self) -> bool:
        return self.estado == EstadoExportacion.COMPLETADO.value


@dataclass
class ConfiguracionExportacion:
    """Parámetros operativos del poller y del umbral síncrono/asíncrono."""

    num_workers_max: int = 2
    max_reintentos: int = 3
    umbral_exportacion_async: int = 10_000
    limite_concurrencia: int = 3
    intervalo_poll_segundos: int = 15
    es_activo: bool = True


@dataclass
class ResultadoExportacion:
    """CSV ya generado de un trabajo completado."""

    contenido_csv: str
    nombre_archivo: str
    total_exportado: int
    total_disponible: int

# | Fecha      | Nombre   | Que se hizo                                                      |
# |------------|----------|------------------------------------------------------------------|
# | 2026-11-14 | Arekkazu | M08 RF-105: nivel, estado, módulo, ocurrencias y acción documentada |
"""Schemas HTTP para la bandeja de notificaciones internas."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from src.shared.base_dto import BaseDTO


class NotificacionInternaResponse(BaseModel):
    """Notificación visible para su usuario destinatario."""

    id_notificacion: int
    id_evento: int
    tipo_evento: int
    mensaje: str
    fecha_envio: datetime
    es_leido: bool
    # RF-105. ``modulo`` es una clave (telemetria, finanzas…) que el front traduce a su nombre.
    nivel: str
    estado: str
    modulo: Optional[str] = None
    url: Optional[str] = None
    ocurrencias: int = 1
    fecha_ultima_ocurrencia: Optional[datetime] = None
    fecha_lectura: Optional[datetime] = None
    fecha_atencion: Optional[datetime] = None
    accion_documentada: Optional[str] = None
    puede_descartarse: bool = False
    puede_atenderse: bool = False

    model_config = {"from_attributes": True}


class AtenderNotificacionDTO(BaseDTO):
    """Qué se hizo. Obligatorio en una alerta crítica (20+ caracteres que digan algo)."""
    accion_documentada: Optional[str] = Field(default=None, max_length=1000)


class MarcadasLeidasResponse(BaseModel):
    """Cuántas notificaciones pasaron a leídas (T-08)."""

    marcadas: int


class NotificacionesPaginadasResponse(BaseModel):
    """Página de notificaciones internas con contador global de no leídas."""

    total: int
    no_leidas: int
    # Críticas sin atender: el dashboard muestra un aviso fijo mientras haya alguna (RF-103 FA-3).
    criticas_pendientes: int = 0
    pagina: int
    tamano: int
    items: list[NotificacionInternaResponse]

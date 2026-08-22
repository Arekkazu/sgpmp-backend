"""Schemas HTTP para la bandeja de notificaciones internas."""
from datetime import datetime

from pydantic import BaseModel


class NotificacionInternaResponse(BaseModel):
    """Notificación visible para su usuario destinatario."""

    id_notificacion: int
    id_evento: int
    tipo_evento: int
    mensaje: str
    fecha_envio: datetime
    es_leido: bool

    model_config = {"from_attributes": True}


class NotificacionesPaginadasResponse(BaseModel):
    """Página de notificaciones internas con contador global de no leídas."""

    total: int
    no_leidas: int
    pagina: int
    tamano: int
    items: list[NotificacionInternaResponse]

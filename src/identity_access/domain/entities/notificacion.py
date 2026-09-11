"""Entidad de dominio para una notificación interna de usuario."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(eq=False)
class Notificacion:
    """Notificación persistida en la bandeja interna de un usuario."""

    id_notificacion: int
    id_evento: int
    tipo_evento: int
    id_usuario: int
    mensaje: str
    fecha_envio: datetime
    es_leido: bool
    estado_envio: str

    def marcar_como_leida(self) -> None:
        """Marca la notificación como leída de forma idempotente."""
        self.es_leido = True

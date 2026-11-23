# | Fecha      | Nombre   | Que se hizo                                                      |
# |------------|----------|------------------------------------------------------------------|
# | 2026-11-14 | Arekkazu | M08 RF-105: nivel, estado, módulo, ocurrencias y acción documentada |
# | 2026-11-18 | Arekkazu | M08 RF-105 R6: preferencias de canal por nivel |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Schemas HTTP para la bandeja de notificaciones internas."""
from datetime import datetime
from typing import Literal, Optional

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


class PreferenciaNotificacionResponse(BaseModel):
    """Un canal de un nivel. IN_APP siempre habilitado y no editable; ``por_defecto`` = sin preferencia guardada."""
    nivel: str
    canal: str
    habilitado: bool
    por_defecto: bool
    editable: bool


class CambioPreferenciaDTO(BaseDTO):
    """Cambio de preferencia de un nivel y canal."""
    nivel: Literal["CRITICA", "ADVERTENCIA", "INFORMATIVA"]
    canal: Literal["PUSH", "EMAIL"]
    habilitado: bool


class GuardarPreferenciasDTO(BaseDTO):
    """Cambios de preferencias de notificación a guardar."""
    preferencias: list[CambioPreferenciaDTO] = Field(min_length=1, max_length=6)


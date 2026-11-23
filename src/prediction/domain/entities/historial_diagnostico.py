# | Fecha      | Nombre   | Que se hizo                                                |
# |------------|----------|------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M04-223-G034 RF-68: evento CONTAGIO sin inferencia     |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Entidades del historial diagnóstico de un activo."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class EventoHistorial:
    """Evento del historial diagnóstico."""
    id_evento: uuid.UUID
    tipo_evento: str
    id_activo_biologico: int
    fecha_evento: datetime
    id_resultado_inferencia: Optional[uuid.UUID]  # None en CONTAGIO (RF-68 no parte de una inferencia)
    payload: dict


@dataclass
class PaginaHistorial:
    """Página del historial con su cursor siguiente."""
    eventos: list[EventoHistorial]
    cursor_siguiente: Optional[str]
    total_pagina: int

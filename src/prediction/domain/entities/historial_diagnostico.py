# | Fecha      | Nombre   | Que se hizo                                                |
# |------------|----------|------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M04-223-G034 RF-68: evento CONTAGIO sin inferencia     |
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class EventoHistorial:
    id_evento: uuid.UUID
    tipo_evento: str
    id_activo_biologico: int
    fecha_evento: datetime
    id_resultado_inferencia: Optional[uuid.UUID]  # None en CONTAGIO (RF-68 no parte de una inferencia)
    payload: dict


@dataclass
class PaginaHistorial:
    eventos: list[EventoHistorial]
    cursor_siguiente: Optional[str]
    total_pagina: int

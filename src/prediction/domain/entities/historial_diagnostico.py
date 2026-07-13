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
    id_resultado_inferencia: uuid.UUID
    payload: dict


@dataclass
class PaginaHistorial:
    eventos: list[EventoHistorial]
    cursor_siguiente: Optional[str]
    total_pagina: int

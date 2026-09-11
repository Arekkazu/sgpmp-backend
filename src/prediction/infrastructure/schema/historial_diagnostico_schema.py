from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from src.prediction.domain.entities.historial_diagnostico import EventoHistorial, PaginaHistorial


class EventoHistorialResponse(BaseModel):
    id_evento: uuid.UUID
    tipo_evento: str
    id_activo_biologico: int
    fecha_evento: datetime
    id_resultado_inferencia: uuid.UUID
    payload: dict

    model_config = {"from_attributes": True}

    @classmethod
    def from_entity(cls, e: EventoHistorial) -> "EventoHistorialResponse":
        return cls(
            id_evento=e.id_evento,
            tipo_evento=e.tipo_evento,
            id_activo_biologico=e.id_activo_biologico,
            fecha_evento=e.fecha_evento,
            id_resultado_inferencia=e.id_resultado_inferencia,
            payload=e.payload,
        )


class HistorialDiagnosticoResponse(BaseModel):
    eventos: list[EventoHistorialResponse]
    cursor_siguiente: Optional[str]
    total_pagina: int

    @classmethod
    def from_pagina(cls, pagina: PaginaHistorial) -> "HistorialDiagnosticoResponse":
        return cls(
            eventos=[EventoHistorialResponse.from_entity(e) for e in pagina.eventos],
            cursor_siguiente=pagina.cursor_siguiente,
            total_pagina=pagina.total_pagina,
        )

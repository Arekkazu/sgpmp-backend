from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import ConfigDict

from src.shared.base_dto import BaseDTO


class EventoAuditoriaM04Response(BaseDTO):
    model_config = ConfigDict(from_attributes=True)

    id_evento: uuid.UUID
    tipo_evento: str
    modulo: str
    fecha_evento: datetime
    tipo_actor: str
    correlacion_id: uuid.UUID
    payload_evento: dict[str, Any]
    es_payload_truncado: bool
    severidad_evento: str
    origen_registro: str
    id_usuario: Optional[int] = None
    id_sistema: Optional[str] = None
    id_referencia: Optional[str] = None
    entidad_referencia: Optional[str] = None
    resultado_operacion: Optional[str] = None
    codigo_error: Optional[str] = None
    descripcion_error: Optional[str] = None
    origen_dato: Optional[str] = None
    version_modelo: Optional[str] = None
    latencia_ms: Optional[int] = None
    hash_evento: Optional[str] = None


class AuditoriaM04ListResponse(BaseDTO):
    total: int
    pagina: int
    por_pagina: int
    items: list[EventoAuditoriaM04Response]

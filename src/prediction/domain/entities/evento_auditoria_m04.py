from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass(frozen=True)
class EventoAuditoriaM04:
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
    id_usuario: Optional[int]
    id_sistema: Optional[str]
    id_referencia: Optional[str]
    entidad_referencia: Optional[str]
    resultado_operacion: Optional[str]
    codigo_error: Optional[str]
    descripcion_error: Optional[str]
    origen_dato: Optional[str]
    version_modelo: Optional[str]
    latencia_ms: Optional[int]
    hash_evento: Optional[str]

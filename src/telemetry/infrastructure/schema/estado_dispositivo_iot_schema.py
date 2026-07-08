from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel


class HistoricoTransicionSchema(BaseModel):
    id_transaccion: int
    id_dispositivo_iot: int
    estado_anterior: str
    estado_nuevo: str
    causa_primaria: Optional[str] = None
    causa_secundaria: Optional[Any] = None
    id_usuario_responsable: Optional[int] = None
    notas: Optional[str] = None
    fecha_transicion: datetime

    model_config = {'from_attributes': True}


class EstadoDispositivoIoTSchema(BaseModel):
    id_estado_dispositivo_iot: int
    id_dispositivo_iot: int
    estado_actual: str
    fecha_ultimo_contacto: Optional[datetime] = None
    id_ultimo_heartbeat: Optional[int] = None
    tiempo_sin_contacto: Optional[int] = None
    causa_primaria: Optional[str] = None
    causas_secundarias: Optional[Any] = None
    fecha_ultima_actualizacion: datetime

    model_config = {'from_attributes': True}


class EstadoDispositivoDetalleSchema(BaseModel):
    estado: EstadoDispositivoIoTSchema
    historial: List[HistoricoTransicionSchema]

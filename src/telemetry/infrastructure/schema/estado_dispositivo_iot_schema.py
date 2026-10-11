from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

from pydantic import BaseModel, Field, model_validator


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
    tiempo_sin_contacto: Optional[int] = Field(
        default=None,
        description=(
            "Segundos transcurridos desde fecha_ultimo_contacto, calculados al responder. "
            "La columna de BD guarda solo el valor de la última transición de estado."
        ),
    )
    causa_primaria: Optional[str] = None
    causas_secundarias: Optional[Any] = None
    fecha_ultima_actualizacion: datetime

    model_config = {'from_attributes': True}

    @model_validator(mode='after')
    def _tiempo_sin_contacto_en_vivo(self) -> EstadoDispositivoIoTSchema:
        # INC-M09-70-G29: el valor guardado se congelaba en la última transición
        # (p. ej. 354 s) mientras el dispositivo seguía sin señal.
        if self.fecha_ultimo_contacto is not None:
            transcurrido = datetime.now(timezone.utc) - self.fecha_ultimo_contacto
            self.tiempo_sin_contacto = max(0, int(transcurrido.total_seconds()))
        return self


class EstadoDispositivoDetalleSchema(BaseModel):
    estado: EstadoDispositivoIoTSchema
    historial: List[HistoricoTransicionSchema]

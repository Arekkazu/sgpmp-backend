# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-31 | Arekkazu | RF-71: aviso de datos insuficientes para reentrenar el modelo individual |
# | 2026-10-31 | Arekkazu | RF-71/RF-73: respuesta de la solicitud de reentrenamiento |
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel

from src.prediction.domain.entities.estado_reentrenamiento import EstadoReentrenamiento


class EstadoReentrenamientoResponse(BaseModel):
    tipo_modelo: str
    #: Resultados de inferencia con retroalimentación RF-72 desde la última versión del modelo.
    registros_nuevos: int
    #: Fecha de la última versión del modelo (null: todavía no hay versión, cuenta todo).
    desde: Optional[datetime]
    estado: Literal["INSUFICIENTE", "PUEDE_SOLICITARSE", "LISTO"]
    #: Registros que faltan para el siguiente estado (0 si ya está LISTO).
    faltan: int
    minimo_solicitud: int
    minimo_reentrenamiento: int

    @classmethod
    def from_entity(cls, e: EstadoReentrenamiento) -> "EstadoReentrenamientoResponse":
        return cls(tipo_modelo=e.tipo_modelo, registros_nuevos=e.registros_nuevos, desde=e.desde,
                   estado=e.estado, faltan=e.faltan, minimo_solicitud=e.minimo_solicitud,
                   minimo_reentrenamiento=e.minimo_reentrenamiento)


class SolicitudReentrenamientoResponse(BaseModel):
    #: Evento REENTRENAMIENTO_SOLICITADO en la bitácora de M04 (RF-73).
    id_evento: UUID
    estado: EstadoReentrenamientoResponse

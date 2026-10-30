# | Fecha      | Nombre   | Que se hizo                                                  |
# |------------|----------|--------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M04-229-G070 RF-72: ampliación de ventana por resultado  |
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class AmpliacionVentanaRetroalimentacionResponse(BaseModel):
    id_ampliacion_ventana_retroalimentacion: int
    id_resultado_inferencia: uuid.UUID
    fecha_limite: datetime
    justificacion: str
    id_usuario_autorizador: int

    model_config = {"from_attributes": True}

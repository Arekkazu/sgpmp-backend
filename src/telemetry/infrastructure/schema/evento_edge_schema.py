# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-26 | Leandro | INC-M03-110-G42 RF-55/RF-56: exponer ambos timestamps originales en la respuesta del evento. |
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class EventoEdgeResponse(BaseModel):
    id_evento_edge_computing: int
    clasificacion_rf55: str
    severidad: Optional[str]
    estado_conectividad: bool
    fecha_captura: datetime
    fecha_procesamiento: datetime
    paquete_inferencia_estado: Optional[str]

    model_config = {"from_attributes": True}

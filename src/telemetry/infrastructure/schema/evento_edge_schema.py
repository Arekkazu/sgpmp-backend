from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class EventoEdgeResponse(BaseModel):
    id_evento_edge_computing: int
    clasificacion_rf55: str
    severidad: Optional[str]
    estado_conectividad: bool
    fecha_procesamiento: datetime
    paquete_inferencia_estado: Optional[str]

    model_config = {"from_attributes": True}

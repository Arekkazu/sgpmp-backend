# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-26 | Leandro | INC-M03-110-G42 RF-55/RF-56: exponer ambos timestamps originales en la respuesta del evento. |
# | 2026-10-27 | destroyerban | INC-M03-118-G61 RF-55: latencia de deteccion medida en el Edge y SLA de 500 ms |
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EventoEdgeResponse(BaseModel):
    id_evento_edge_computing: int
    clasificacion_rf55: str
    severidad: Optional[str]
    estado_conectividad: bool
    fecha_captura: datetime
    fecha_procesamiento: datetime
    paquete_inferencia_estado: Optional[str]
    latencia_edge_ms: Optional[int] = Field(
        default=None, description="RF-55: timestamp_procesamiento_edge − timestamp_captura, en ms (reloj del nodo).")
    sla_edge_excedido: Optional[bool] = Field(
        default=None, description="RF-55 CA-1: true si la detección en el Edge superó 500 ms.")

    model_config = {"from_attributes": True}

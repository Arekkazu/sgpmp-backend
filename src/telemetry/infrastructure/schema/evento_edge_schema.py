# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-26 | Leandro | INC-M03-110-G42 RF-55/RF-56: exponer ambos timestamps originales en la respuesta del evento. |
# | 2026-10-26 | destroyerban | INC-M03-111-G43 RF-55.1: guarda valor y umbrales aplicados por el Edge |
from datetime import datetime
from decimal import Decimal
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
    valor_evaluado: Optional[Decimal] = None
    umbral_min_aplicado: Optional[Decimal] = None
    umbral_max_aplicado: Optional[Decimal] = None

    model_config = {"from_attributes": True}

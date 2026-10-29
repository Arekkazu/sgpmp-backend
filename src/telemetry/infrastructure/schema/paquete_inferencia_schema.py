# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-27 | destroyerban | INC-M03-116-G59 RF-56: consulta del paquete por id con alcance por finca |
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field

from src.telemetry.infrastructure.schema.bitacora_auditoria_iot_schema import EventoAuditoriaIotSchema


class PaqueteInferenciaDetalleSchema(BaseModel):
    """Paquete RF-56 con su trazabilidad y su ciclo de vida (bitácora RF-63, CA-8)."""

    id_paquete_inferencia: int
    # Trazabilidad end-to-end (Postcondición 3): sensor → evento Edge → paquete → versión de modelo.
    id_sensor: int
    id_dispositivo_iot: int
    id_evento_edge_computing: int
    id_version_modelo: Optional[int]
    tipo_variable: str
    valor_numerico: Decimal
    unidad: Optional[str]
    estado_calidad: str
    estado_desviacion: Optional[str]
    severidad: Optional[str]
    origen: Optional[str]
    contexto_incompleto: bool
    contexto_ambiental: Optional[dict[str, Any]]
    metadatos: Optional[dict[str, Any]]
    estado_paquete: str = Field(description="ENVIADO | PENDIENTE | FALLIDO")
    intento_envios: int
    fecha_envio: datetime = Field(
        description="Fecha de envío registrada: la de generación del paquete o, con la política de "
                    "reintentos de RF-56 (#656), la del último intento.")
    ciclo_vida: list[EventoAuditoriaIotSchema] = Field(
        description="Eventos de la bitácora RF-63 sobre este paquete, en orden cronológico.")

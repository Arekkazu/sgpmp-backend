# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-126-G27 RF-54: validar métricas opcionales y capacidades coherentes en la misma unidad reportada. |
from decimal import Decimal
from pydantic import ConfigDict, Field, model_validator
from src.shared.base_dto import BaseDTO
from src.shared.fechas import FechaHoraUtc
from src.telemetry.domain.entities.estado_buffer import MetricasBuffer, PoliticaBuffer


class MetricasBufferDTO(BaseDTO):
    model_config = ConfigDict(extra='forbid')
    capacidad_total: Decimal = Field(gt=0, allow_inf_nan=False, description='Capacidad en la misma unidad que capacidad_utilizada, reportada por Edge.')
    capacidad_utilizada: Decimal = Field(ge=0, allow_inf_nan=False)
    ultimo_timestamp_pendiente: FechaHoraUtc | None
    politica_buffer_activa: PoliticaBuffer

    @model_validator(mode='after')
    def validar_capacidades(self):
        self.a_dominio()
        return self

    def a_dominio(self) -> MetricasBuffer:
        return MetricasBuffer(self.capacidad_total, self.capacidad_utilizada,
                              self.ultimo_timestamp_pendiente, self.politica_buffer_activa)

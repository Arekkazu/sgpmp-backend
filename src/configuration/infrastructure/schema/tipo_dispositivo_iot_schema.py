"""Schemas de respuesta para tipos de dispositivo IoT y sus rangos (RF-23)."""
from __future__ import annotations

from pydantic import BaseModel


class TipoDispositivoIotResponse(BaseModel):
    id_tipo_dispositivo: int
    nombre: str
    frecuencia_captura_min: int
    frecuencia_captura_max: int
    intervalo_transmision_min: int
    intervalo_transmision_max: int

    @classmethod
    def from_entity(cls, tipo) -> TipoDispositivoIotResponse:
        return cls(
            id_tipo_dispositivo=tipo.id_tipo_dispositivo,
            nombre=tipo.nombre,
            frecuencia_captura_min=tipo.frecuencia_captura_min,
            frecuencia_captura_max=tipo.frecuencia_captura_max,
            intervalo_transmision_min=tipo.intervalo_transmision_min,
            intervalo_transmision_max=tipo.intervalo_transmision_max,
        )


class ListaTiposDispositivoIotResponse(BaseModel):
    total: int
    items: list[TipoDispositivoIotResponse]

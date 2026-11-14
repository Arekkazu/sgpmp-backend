# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
"""DTO de entrada para actualizar la configuración operativa global (PATCH RF-18).

Incluye ``fecha_actualizacion`` como token de concurrencia optimista.
"""

from pydantic import AliasChoices, Field, field_validator, model_validator

from src.shared.base_dto import BaseDTO
from .alias_umbral_sin_senal import validar_alias_umbral
from src.shared.fechas import FechaHoraUtc


class ActualizarConfiguracionDTO(BaseDTO):
    """Nuevos minutos de frecuencia de muestreo y heartbeat (heartbeat >= frecuencia).

    ``fecha_actualizacion`` debe ser la leída del registro (concurrencia optimista, 412 si cambió).
    """
    model_config = {"loc_by_alias": False}

    frecuencia_muestreo: int
    heartbeat: int = Field(validation_alias=AliasChoices('umbral_sin_senal', 'heartbeat'))
    fecha_actualizacion: FechaHoraUtc

    @model_validator(mode='before')
    @classmethod
    def comprobar_alias(cls, datos):
        return validar_alias_umbral(datos)

    @field_validator("frecuencia_muestreo", "heartbeat")
    @classmethod
    def validar_entero_positivo(cls, v: int) -> int:
        if not isinstance(v, int) or isinstance(v, bool) or v <= 0:
            raise ValueError(
                f"Debe ser un número entero positivo mayor a 0. Valor recibido: {v}."
            )
        return v

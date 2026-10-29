"""DTO de entrada para crear la configuración operativa global (POST RF-18)."""
from pydantic import AliasChoices, Field, field_validator, model_validator

from src.shared.base_dto import BaseDTO
from .alias_umbral_sin_senal import validar_alias_umbral


class CrearConfiguracionDTO(BaseDTO):
    """Minutos de frecuencia de muestreo y de heartbeat (heartbeat >= frecuencia)."""
    model_config = {"loc_by_alias": False}

    frecuencia_muestreo: int
    heartbeat: int = Field(validation_alias=AliasChoices('umbral_sin_senal', 'heartbeat'))

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

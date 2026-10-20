"""Sobre D4 v1 con rangos de RFC-011 y catálogo de calibración SQL vigente.

Las diferencias con el sobre ampliado de AIOT-SPEC-01 están documentadas;
no se inventan n_individuos, origen ni equivalencias entre estados.
"""
from decimal import Decimal
from pydantic import AliasChoices, AwareDatetime, ConfigDict, Field, StrictInt, StrictStr, model_validator
from src.shared.base_dto import BaseDTO
from src.telemetry.domain.entities.observacion_vision import EstadoCalibracionCamara


class BloqueVisionDTO(BaseDTO):
    model_config = ConfigDict(extra='forbid')


class ComponentesVisionDTO(BloqueVisionDTO):
    densidad_actividad: Decimal = Field(ge=0, le=1, max_digits=5, decimal_places=4, allow_inf_nan=False)
    dispersion_espacial: Decimal = Field(ge=0, max_digits=8, decimal_places=4, allow_inf_nan=False)
    tasa_movimiento: Decimal = Field(ge=0, max_digits=8, decimal_places=4, allow_inf_nan=False)


class CalidadVisionD4DTO(BloqueVisionDTO):
    cobertura_ventana: Decimal = Field(ge=0, le=1, max_digits=5, decimal_places=4, allow_inf_nan=False)
    n_tracks: StrictInt = Field(ge=0, le=2147483647)
    n_tracks_perdidos: StrictInt = Field(ge=0, le=2147483647)
    fps_efectivo: Decimal = Field(ge=0, max_digits=5, decimal_places=2, allow_inf_nan=False)
    estado_calibracion: EstadoCalibracionCamara


class VersionCascadaDTO(BloqueVisionDTO):
    detector: StrictStr = Field(min_length=1)
    seguimiento: StrictStr = Field(min_length=1)
    metricas: StrictStr = Field(min_length=1)
    anomalias: StrictStr = Field(min_length=1)


class ObservacionVisionD4DTO(BloqueVisionDTO):
    serial: StrictStr = Field(min_length=1, max_length=50, validation_alias=AliasChoices('serial', 'dispositivo_serial'))
    area_id: StrictInt = Field(gt=0)
    ventana_inicio: AwareDatetime
    ventana_fin: AwareDatetime
    componentes: ComponentesVisionDTO
    calidad: CalidadVisionD4DTO = Field(validation_alias=AliasChoices('calidad', 'indicadores_calidad'))
    version_cascada: VersionCascadaDTO

    @model_validator(mode='before')
    @classmethod
    def aliases_sin_ambiguedad(cls, datos):
        if isinstance(datos, dict):
            datos = dict(datos)
            for canonico, alias in (('serial', 'dispositivo_serial'), ('calidad', 'indicadores_calidad')):
                if canonico in datos and alias in datos:
                    if datos[canonico] != datos[alias]:
                        raise ValueError(f'{canonico} y {alias} deben coincidir cuando se proporcionan ambos.')
                    datos.pop(alias)
        return datos

    @model_validator(mode='after')
    def ventana_coherente(self):
        if self.ventana_inicio >= self.ventana_fin:
            raise ValueError('ventana_inicio debe ser anterior a ventana_fin.')
        return self

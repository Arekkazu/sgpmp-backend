# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-28 RF-53/62: sobre normativo separado del contrato legado |
"""Sobres D4 normativo y legado con rangos de RFC-011.

El contrato normativo exige los metadatos de la ficha. El legado conserva su
catalogo historico; no se inventan equivalencias entre estados ni cantidades.
"""
from decimal import Decimal
from typing import Literal
from pydantic import AliasChoices, AwareDatetime, ConfigDict, Field, StrictInt, StrictStr, model_validator
from src.shared.base_dto import BaseDTO
from src.telemetry.domain.entities.observacion_vision import EstadoCalibracionCamara
from src.telemetry.domain.entities.calidad_vision import EstadoCalibracionVision


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


class ObservacionVisionD4LegadoDTO(BloqueVisionDTO):
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


class CalidadVisionFichaDTO(CalidadVisionD4DTO):
    # P-5 no se resuelve derivando tracks a partir del numero de individuos.
    n_tracks: StrictInt | None = Field(default=None, ge=0, le=2147483647)
    estado_calibracion: EstadoCalibracionVision


class ObservacionVisionD4DTO(ObservacionVisionD4LegadoDTO):
    tipo_dato: Literal['VECTOR_COMPORTAMIENTO']
    n_individuos_observados: StrictInt = Field(ge=0, le=2147483647)
    origen: Literal['TIEMPO_REAL', 'BUFFER_LOCAL']
    calidad: CalidadVisionFichaDTO = Field(validation_alias=AliasChoices('calidad', 'indicadores_calidad'))

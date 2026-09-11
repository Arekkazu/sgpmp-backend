from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict

from src.prediction.domain.entities.configuracion_motor_ia import ConfiguracionMotorIA


class ConfiguracionMotorIAResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_configuracion_motor: int
    tipo_modelo: str
    umbral_riesgo_alto: Decimal
    umbral_alerta_critica: Decimal
    ventana_temporal_min: int
    modo_ejecucion: str
    id_version_modelo_activa: Optional[int] = None
    config_version: int
    w_factor_sanitario: Decimal
    w_factor_ambiental: Decimal
    w_factor_densidad: Decimal
    temp_min_config: Optional[Decimal] = None
    temp_max_config: Optional[Decimal] = None
    hr_min_config: Optional[Decimal] = None
    hr_max_config: Optional[Decimal] = None
    densidad_maxima_config: Optional[Decimal] = None
    es_activa: bool
    id_usuario_responsable: int
    fecha_creacion: datetime

    @classmethod
    def from_entity(cls, entidad: ConfiguracionMotorIA) -> ConfiguracionMotorIAResponse:
        return cls(
            id_configuracion_motor=entidad.id_configuracion_motor,
            tipo_modelo=entidad.tipo_modelo,
            umbral_riesgo_alto=entidad.umbral_riesgo_alto,
            umbral_alerta_critica=entidad.umbral_alerta_critica,
            ventana_temporal_min=entidad.ventana_temporal_min,
            modo_ejecucion=entidad.modo_ejecucion,
            id_version_modelo_activa=entidad.id_version_modelo_activa,
            config_version=entidad.config_version,
            w_factor_sanitario=entidad.w_factor_sanitario,
            w_factor_ambiental=entidad.w_factor_ambiental,
            w_factor_densidad=entidad.w_factor_densidad,
            temp_min_config=entidad.temp_min_config,
            temp_max_config=entidad.temp_max_config,
            hr_min_config=entidad.hr_min_config,
            hr_max_config=entidad.hr_max_config,
            densidad_maxima_config=entidad.densidad_maxima_config,
            es_activa=entidad.es_activa,
            id_usuario_responsable=entidad.id_usuario_responsable,
            fecha_creacion=entidad.fecha_creacion,
        )


class ConfiguracionMotorIAListResponse(BaseModel):
    total: int
    items: list[ConfiguracionMotorIAResponse]

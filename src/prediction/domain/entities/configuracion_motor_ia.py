from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass(eq=False)
class ConfiguracionMotorIA:
    tipo_modelo: str
    umbral_riesgo_alto: Decimal
    umbral_alerta_critica: Decimal
    ventana_temporal_min: int
    modo_ejecucion: str
    w_factor_sanitario: Decimal
    w_factor_ambiental: Decimal
    w_factor_densidad: Decimal
    id_usuario_responsable: int
    config_version: int = 1
    es_activa: bool = True
    id_configuracion_motor: Optional[int] = None
    id_version_modelo_activa: Optional[int] = None
    temp_min_config: Optional[Decimal] = None
    temp_max_config: Optional[Decimal] = None
    hr_min_config: Optional[Decimal] = None
    hr_max_config: Optional[Decimal] = None
    densidad_maxima_config: Optional[Decimal] = None
    fecha_creacion: Optional[datetime] = None

    @classmethod
    def crear(
        cls,
        *,
        tipo_modelo: str,
        umbral_riesgo_alto: Decimal,
        umbral_alerta_critica: Decimal,
        ventana_temporal_min: int,
        modo_ejecucion: str,
        w_factor_sanitario: Decimal,
        w_factor_ambiental: Decimal,
        w_factor_densidad: Decimal,
        id_usuario_responsable: int,
        id_version_modelo_activa: Optional[int] = None,
        temp_min_config: Optional[Decimal] = None,
        temp_max_config: Optional[Decimal] = None,
        hr_min_config: Optional[Decimal] = None,
        hr_max_config: Optional[Decimal] = None,
        densidad_maxima_config: Optional[Decimal] = None,
    ) -> ConfiguracionMotorIA:
        return cls(
            tipo_modelo=tipo_modelo,
            umbral_riesgo_alto=umbral_riesgo_alto,
            umbral_alerta_critica=umbral_alerta_critica,
            ventana_temporal_min=ventana_temporal_min,
            modo_ejecucion=modo_ejecucion,
            w_factor_sanitario=w_factor_sanitario,
            w_factor_ambiental=w_factor_ambiental,
            w_factor_densidad=w_factor_densidad,
            id_usuario_responsable=id_usuario_responsable,
            id_version_modelo_activa=id_version_modelo_activa,
            temp_min_config=temp_min_config,
            temp_max_config=temp_max_config,
            hr_min_config=hr_min_config,
            hr_max_config=hr_max_config,
            densidad_maxima_config=densidad_maxima_config,
            config_version=1,
            es_activa=True,
        )

    def actualizar(
        self,
        *,
        umbral_riesgo_alto: Decimal,
        umbral_alerta_critica: Decimal,
        ventana_temporal_min: int,
        modo_ejecucion: str,
        w_factor_sanitario: Decimal,
        w_factor_ambiental: Decimal,
        w_factor_densidad: Decimal,
        id_usuario_responsable: int,
        id_version_modelo_activa: Optional[int] = None,
        temp_min_config: Optional[Decimal] = None,
        temp_max_config: Optional[Decimal] = None,
        hr_min_config: Optional[Decimal] = None,
        hr_max_config: Optional[Decimal] = None,
        densidad_maxima_config: Optional[Decimal] = None,
    ) -> None:
        self.umbral_riesgo_alto = umbral_riesgo_alto
        self.umbral_alerta_critica = umbral_alerta_critica
        self.ventana_temporal_min = ventana_temporal_min
        self.modo_ejecucion = modo_ejecucion
        self.w_factor_sanitario = w_factor_sanitario
        self.w_factor_ambiental = w_factor_ambiental
        self.w_factor_densidad = w_factor_densidad
        self.id_usuario_responsable = id_usuario_responsable
        self.id_version_modelo_activa = id_version_modelo_activa
        self.temp_min_config = temp_min_config
        self.temp_max_config = temp_max_config
        self.hr_min_config = hr_min_config
        self.hr_max_config = hr_max_config
        self.densidad_maxima_config = densidad_maxima_config
        self.config_version += 1

    def _snapshot(self) -> dict:
        return {
            "tipo_modelo": self.tipo_modelo,
            "umbral_riesgo_alto": str(self.umbral_riesgo_alto),
            "umbral_alerta_critica": str(self.umbral_alerta_critica),
            "ventana_temporal_min": self.ventana_temporal_min,
            "modo_ejecucion": self.modo_ejecucion,
            "id_version_modelo_activa": self.id_version_modelo_activa,
            "config_version": self.config_version,
            "w_factor_sanitario": str(self.w_factor_sanitario),
            "w_factor_ambiental": str(self.w_factor_ambiental),
            "w_factor_densidad": str(self.w_factor_densidad),
            "temp_min_config": str(self.temp_min_config) if self.temp_min_config is not None else None,
            "temp_max_config": str(self.temp_max_config) if self.temp_max_config is not None else None,
            "hr_min_config": str(self.hr_min_config) if self.hr_min_config is not None else None,
            "hr_max_config": str(self.hr_max_config) if self.hr_max_config is not None else None,
            "densidad_maxima_config": str(self.densidad_maxima_config) if self.densidad_maxima_config is not None else None,
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ConfiguracionMotorIA):
            return NotImplemented
        if self.id_configuracion_motor is None or other.id_configuracion_motor is None:
            return self is other
        return self.id_configuracion_motor == other.id_configuracion_motor

    def __hash__(self) -> int:
        return hash(self.id_configuracion_motor)

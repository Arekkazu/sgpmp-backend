# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-02 | Arekkazu | AJF-04 RF-60: respuesta de parámetros de heartbeat y ventanas de visión |
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, computed_field


class ParametrosHeartbeatCategoriaSchema(BaseModel):
    """Segundos. None = no configurado (lo define el Administrador en Configuración)."""
    model_config = ConfigDict(from_attributes=True)

    categoria: str
    intervalo_heartbeat_seg: Optional[int]
    frecuencia_muestreo_seg: Optional[int]
    margen_tolerancia_seg: Optional[int]
    umbral_sin_senal_seg: Optional[int]
    umbral_inactivo_seg: Optional[int]
    cadena_valida: Optional[bool]
    faltantes: list[str]

    @computed_field
    @property
    def configurado(self) -> bool:
        return not self.faltantes


class VentanaVisionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_observacion_vision: int
    inicio: Optional[datetime]
    fin: datetime
    cobertura: Decimal
    n_individuos: Optional[int]


class VentanasVisionSchema(BaseModel):
    """``resultado``: DETECCION_VALIDA | SIN_DETECCION_VALIDA | SIN_VENTANAS | SIN_CONFIGURAR | NO_ES_CAMARA."""
    model_config = ConfigDict(from_attributes=True)

    id_dispositivo_iot: int
    es_camara: bool
    ventanas: list[VentanaVisionSchema]
    ventanas_consecutivas: Optional[int]
    cobertura_minima: Optional[Decimal]
    duracion_seg: Optional[int]
    consecutivas_bajo_minimo: int
    resultado: str

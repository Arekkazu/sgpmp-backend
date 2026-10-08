"""Schemas de respuesta de la calibración por visión (RF-24 v2.0)."""
from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel

from src.configuration.domain.value_objects.calibracion_vision import (
    EstadoCalibracionVision,
    EtapaCalibracionVision,
    OrigenDisparo,
)
from src.configuration.domain.value_objects.modo_calibracion import ModoCalibracion


class LineaBaseValoresResponse(BaseModel):
    # Mediana de referencia por componente del vector de comportamiento.
    valores: dict[str, float]
    componentes_no_calibrables: list[str]


class CalibracionVisionResponse(BaseModel):
    id_calibracion_vision: int
    modo_calibracion: ModoCalibracion = ModoCalibracion.VISION
    area_id: int
    especie_id: int
    origen_disparo: OrigenDisparo
    id_usuario: Optional[int]
    ventana_observacion: dict
    fecha_calibracion: datetime.datetime
    estado: EstadoCalibracionVision
    etapa_fallo: Optional[EtapaCalibracionVision]
    motivo: Optional[str]
    linea_base: Optional[LineaBaseValoresResponse]
    n_observaciones: int
    n_observaciones_validas: int
    iteraciones: Optional[int]
    observaciones: Optional[str]

    @classmethod
    def from_entity(cls, calibracion) -> "CalibracionVisionResponse":
        return cls(
            id_calibracion_vision=calibracion.id_calibracion_vision,
            area_id=calibracion.id_infraestructura,
            especie_id=calibracion.id_especie,
            origen_disparo=calibracion.origen_disparo,
            id_usuario=calibracion.id_usuario,
            ventana_observacion=calibracion.ventana_observacion,
            fecha_calibracion=calibracion.fecha_calibracion,
            estado=calibracion.estado,
            etapa_fallo=calibracion.etapa_fallo,
            motivo=calibracion.motivo,
            linea_base=calibracion.linea_base,
            n_observaciones=calibracion.n_observaciones,
            n_observaciones_validas=calibracion.n_observaciones_validas,
            iteraciones=calibracion.iteraciones,
            observaciones=calibracion.observaciones,
        )


class ListaCalibracionesVisionResponse(BaseModel):
    total: int
    items: list[CalibracionVisionResponse]


class LineaBaseVisionResponse(BaseModel):
    area_id: int
    especie_id: int
    id_calibracion_vision: int
    linea_base: LineaBaseValoresResponse
    fecha_publicacion: datetime.datetime

    @classmethod
    def from_entity(cls, linea_base) -> "LineaBaseVisionResponse":
        return cls(
            area_id=linea_base.id_infraestructura,
            especie_id=linea_base.id_especie,
            id_calibracion_vision=linea_base.id_calibracion_vision,
            linea_base=linea_base.valor,
            fecha_publicacion=linea_base.fecha_publicacion,
        )

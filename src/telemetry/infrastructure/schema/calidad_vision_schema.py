# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-03 | Arekkazu | RF-62: listado de observaciones de visión evaluadas (el panel mostraba datos de ejemplo) |
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ObservacionVisionEvaluadaSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_observacion_vision: int
    id_dispositivo_iot: int
    serial_camara: Optional[str] = None
    id_infraestructura: int
    nombre_area: Optional[str] = None
    fecha_inicio_ventana: Optional[datetime] = None
    fecha_observacion: datetime
    n_individuos_observados: Optional[int] = None
    cobertura_ventana: Decimal
    fps_efectivo: Decimal
    cantidad_tracks_perdidos: int
    #: CALIBRADO | EN_CALIBRACION | SIN_LINEA_BASE.
    estado_calibracion: str
    #: Sin evaluar todavía (proceso asíncrono): índice, clase y aptitud en null.
    indice_calidad_vision: Optional[Decimal] = None
    clasificacion_calidad: Optional[str] = None
    es_apto_para_ia: Optional[bool] = None
    es_confianza_baja: Optional[bool] = None
    #: Visión nunca es apta para NIC 41 (RF-62): M06 no usa conteos de cámara.
    apto_para_nic41: bool = False
    flags_detectados: Optional[dict] = None
    fecha_evaluacion_calidad: Optional[datetime] = None


class PoliticaVisionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    w1: Decimal
    w2: Decimal
    w3: Decimal
    tracks_perdidos_tolerables: int
    umbral_optima: Decimal
    umbral_degradada: Decimal
    factor_en_calibracion: Decimal


class ListaCalidadVisionSchema(BaseModel):
    items: list[ObservacionVisionEvaluadaSchema]
    total: int
    pagina: int
    por_pagina: int
    desde: datetime
    hasta: datetime
    #: Política vigente en M09; null si falta o es inválida (``politica_motivo`` dice por qué).
    politica: Optional[PoliticaVisionSchema] = None
    politica_motivo: Optional[str] = None

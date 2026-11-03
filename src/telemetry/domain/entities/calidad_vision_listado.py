# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-03 | Arekkazu | RF-62: listado de observaciones de visión evaluadas (el panel mostraba datos de ejemplo) |
"""Read-models del panel de calidad de visión (RF-62, Telemetría → Calidad).

El panel calculaba el índice en el navegador sobre cuatro observaciones inventadas. La evaluación
real la hace el backend después de la ingesta (``ObservacionVision.evaluar``) y queda en
``modulo3.observaciones_vision``: aquí solo se lee, sin recalcular.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

CLASES_VISION = ("OPTIMA", "DEGRADADA", "NO_APTA")
#: Filtro extra: observaciones que aún esperan su evaluación asíncrona.
SIN_EVALUAR = "SIN_EVALUAR"


@dataclass(frozen=True)
class FiltrosCalidadVision:
    desde: datetime
    hasta: datetime
    ids_fincas: Optional[list[int]]
    id_dispositivo_iot: Optional[int] = None
    clasificacion: Optional[str] = None
    pagina: int = 1
    por_pagina: int = 50


@dataclass(frozen=True)
class ObservacionVisionEvaluada:
    id_observacion_vision: int
    id_dispositivo_iot: int
    serial_camara: Optional[str]
    id_infraestructura: int
    nombre_area: Optional[str]
    fecha_inicio_ventana: Optional[datetime]
    fecha_observacion: datetime
    n_individuos_observados: Optional[int]
    cobertura_ventana: Decimal
    fps_efectivo: Decimal
    cantidad_tracks_perdidos: int
    estado_calibracion: str
    indice_calidad_vision: Optional[Decimal]
    clasificacion_calidad: Optional[str]
    es_apto_para_ia: Optional[bool]
    es_confianza_baja: Optional[bool]
    #: Los cuatro flags con los valores con que se evaluó (FPS configurado, tolerancia…).
    flags_detectados: Optional[dict]
    fecha_evaluacion_calidad: Optional[datetime]


@dataclass(frozen=True)
class PoliticaVisionVigente:
    """Parámetros del índice tal como están hoy en M09 (pueden diferir de los de una evaluación vieja)."""
    w1: Decimal
    w2: Decimal
    w3: Decimal
    tracks_perdidos_tolerables: int
    umbral_optima: Decimal
    umbral_degradada: Decimal
    factor_en_calibracion: Decimal

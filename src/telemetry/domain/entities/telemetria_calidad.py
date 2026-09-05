from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID


class ClasificacionCalidad(str, Enum):
    APTO = 'APTO'
    APTO_CON_RESERVA = 'APTO_CON_RESERVA'
    NO_APTO = 'NO_APTO'
    INDETERMINADA = 'INDETERMINADA'


class EstadoEvaluacion(str, Enum):
    VIGENTE = 'VIGENTE'
    SUPERADA = 'SUPERADA'


# Descuentos por flag según tabla del RF-62 Fase 6
_DESCUENTOS: dict[str, dict] = {
    'sensor_congelado': {'LEVE': 15, 'MODERADO': 35, 'CRITICO': 90},
    'outlier_estadistico': 20,
    'posible_drift': {'<10': 10, '10-20': 25, '>20': 40},
    'gap_temporal_anomalo': 10,
}


def calcular_indice_calidad(flags: dict) -> Optional[int]:
    """Aplica la tabla de descuentos del RF-62 y retorna el índice (0-100).
    Retorna None si serie_insuficiente=True (clasificación INDETERMINADA).
    """
    if flags.get('serie_insuficiente', {}).get('activo', False):
        return None

    descuento = 0

    sc = flags.get('sensor_congelado', {})
    if sc.get('activo', False):
        sev = sc.get('severidad', 'LEVE')
        descuento += _DESCUENTOS['sensor_congelado'].get(sev, 15)

    if flags.get('outlier_estadistico', {}).get('activo', False):
        descuento += _DESCUENTOS['outlier_estadistico']

    drift = flags.get('posible_drift', {})
    if drift.get('activo', False):
        mag = float(drift.get('magnitud_drift_porcentaje', 0))
        if mag > 20:
            descuento += _DESCUENTOS['posible_drift']['>20']
        elif mag >= 10:
            descuento += _DESCUENTOS['posible_drift']['10-20']
        else:
            descuento += _DESCUENTOS['posible_drift']['<10']

    if flags.get('gap_temporal_anomalo', {}).get('activo', False):
        descuento += _DESCUENTOS['gap_temporal_anomalo']

    return max(0, 100 - descuento)


def clasificar_desde_indice(indice: Optional[int]) -> ClasificacionCalidad:
    if indice is None:
        return ClasificacionCalidad.INDETERMINADA
    if indice >= 80:
        return ClasificacionCalidad.APTO
    if indice >= 40:
        return ClasificacionCalidad.APTO_CON_RESERVA
    return ClasificacionCalidad.NO_APTO


def derivar_aptitud(clasificacion: ClasificacionCalidad) -> tuple[bool, bool]:
    """Retorna (apto_para_ia, apto_para_nic41)."""
    if clasificacion == ClasificacionCalidad.APTO:
        return True, True
    if clasificacion == ClasificacionCalidad.APTO_CON_RESERVA:
        return True, False
    return False, False


@dataclass
class TelemetriaCalidad:
    id_evaluacion: Optional[UUID]
    id_telemetria: int
    id_sensor: int
    timestamp_evaluacion: datetime
    indice_calidad: Optional[int]
    clasificacion_calidad: ClasificacionCalidad
    apto_para_ia: bool
    apto_para_nic41: bool
    flags_detectados: dict = field(default_factory=dict)
    version_limites_fisicos_aplicada: Optional[str] = None
    parametros_aplicados: dict = field(default_factory=dict)
    parametros_calibracion_aplicados: Optional[dict] = None
    estado_evaluacion: EstadoEvaluacion = EstadoEvaluacion.VIGENTE
    motivo_reevaluacion: Optional[str] = None
    id_evaluacion_superada: Optional[UUID] = None
    version_evaluacion: Optional[str] = None
    fecha_creacion: Optional[datetime] = None

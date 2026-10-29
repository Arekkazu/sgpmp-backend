"""spec_tc_m03_g165.py — Constantes normativas y especificación oficial (RF-62 / RF-63).

Único bloque centralizado de constantes normativas para TC-M03-G165.
Cada constante tiene su origen especificado según la especificación del sistema.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class SpecDescuentos:
    """Tabla de descuentos por flag según RF-62 Fase 6."""
    sensor_congelado_leve: int = 15
    sensor_congelado_moderado: int = 35
    sensor_congelado_critico: int = 90
    outlier_estadistico: int = 20
    drift_tramo_bajo: int = 10     # < 10%
    drift_tramo_medio: int = 25    # 10% - 20%
    drift_tramo_alto: int = 40     # > 20%
    gap_temporal: int = 10


class SpecUmbrales:
    """Umbrales de clasificación según RF-62 Fase 6."""
    apto_min: int = 80
    apto_con_reserva_min: int = 40
    no_apto_max: int = 39


class SpecParametrosBase:
    """Parámetros base de calidad según RF-62 (hoja 'Parámetros base' y CA-4/CA-5)."""
    N: int = 20
    M: int = 5
    k: float = 3.0
    umbral_drift_pct: float = 5.0
    
    # P=5 en especificación del plan (el código stub adapter tiene P=3).
    # Solo observación D6; sin aserción en el set de pruebas.
    P: int = 5

    intervalo_muestreo_min: int = 10
    gap_temporal_min: int = 25
    outlier_mult_sigma: float = 6.0  # Robusto tanto para desviación muestral como poblacional
    tolerancia_fecha_seg: int = 60


class SpecEstados:
    """D7 RESUELTO: Definido por análisis (respuesta registrada; RFC de aclaración de RF-62 en trámite, nº pendiente). Descartado ACTIVA.
    
    Literal oficial: 'VIGENTE'. Catálogo: {'VIGENTE', 'SUPERADA'}.
    Regla canónica: máximo UNA evaluación VIGENTE por lectura.
    """
    estado_superado: str = "SUPERADA"  # RF-62 restricción 9 y CA-16

    estado_vigente: str = "VIGENTE"  # Definido por análisis (respuesta registrada; RFC de aclaración de RF-62 en trámite, nº pendiente). Descartado ACTIVA.

    catalogo_estados: list[str] = ["VIGENTE", "SUPERADA"]  # Definido por análisis (respuesta registrada; RFC de aclaración de RF-62 en trámite, nº pendiente). Descartado ACTIVA.

    evaluar_supera_anterior: bool = True  # Definido por análisis (respuesta registrada; RFC de aclaración de RF-62 en trámite, nº pendiente). Descartado ACTIVA.

    ESTADOS_DEFINIDOS: bool = True


class SpecAptitud:
    """Tabla de derivación de aptitud según RF-62 Fase 6."""
    @staticmethod
    def derivar(clasificacion: str) -> tuple[bool, bool]:
        if clasificacion == "APTO":
            return True, True
        elif clasificacion == "APTO_CON_RESERVA":
            return True, False
        elif clasificacion in ("NO_APTO", "INDETERMINADA"):
            return False, False
        raise ValueError(f"Clasificación desconocida: {clasificacion}")


# ── ORÁCULO INDEPENDIENTE PURO ──────────────────────────────────────────────

def calcular_indice_esperado(flags_esperados: dict) -> int:
    """Calcula el índice de calidad esperado (0-100) aplicando las reglas normativas puras."""
    descuentos = 0
    if flags_esperados.get("sensor_congelado"):
        sev = flags_esperados["sensor_congelado"]
        if sev == "LEVE":
            descuentos += SpecDescuentos.sensor_congelado_leve
        elif sev == "MODERADO":
            descuentos += SpecDescuentos.sensor_congelado_moderado
        elif sev == "CRITICO":
            descuentos += SpecDescuentos.sensor_congelado_critico

    if flags_esperados.get("outlier_estadistico"):
        descuentos += SpecDescuentos.outlier_estadistico

    if flags_esperados.get("posible_drift") is not None:
        mag = float(flags_esperados["posible_drift"])
        if mag > 20:
            descuentos += SpecDescuentos.drift_tramo_alto
        elif mag >= 10:
            descuentos += SpecDescuentos.drift_tramo_medio
        else:
            descuentos += SpecDescuentos.drift_tramo_bajo

    if flags_esperados.get("gap_temporal_anomalo"):
        descuentos += SpecDescuentos.gap_temporal

    return max(0, 100 - descuentos)


def clasificar_esperado(indice: int) -> str:
    """Determina la clasificación cualitativa esperada a partir del índice."""
    if indice >= SpecUmbrales.apto_min:
        return "APTO"
    if indice >= SpecUmbrales.apto_con_reserva_min:
        return "APTO_CON_RESERVA"
    return "NO_APTO"

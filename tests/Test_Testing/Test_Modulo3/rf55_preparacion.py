"""Datos de la matriz G37–G54 y localización del motor Edge.

No clasifica mediciones. No sustituye firmware AIOT ni POST /iot/eventos-edge.
Los literales salen de la matriz original (G37–G64). La inclusividad 10%/25%
y la ventana 5 s vs 30 s no están resueltas en src/; se dejan anotadas.
"""
from __future__ import annotations

from typing import Any, Optional

import pytest

LATENCIA_MAX_MS_RF55 = 500
PRESUPUESTO_MS_RF552 = 200
MAX_REGLAS_COMPUESTAS_POR_CICLO = 5
FRECUENCIA_MIN_S_RF552 = 5
CARDINALIDAD_MIN = 2
CARDINALIDAD_MAX = 3
HARDWARE_MIN = {"cpu_mhz": 160, "ram_kb": 256, "almacenamiento_mb": 1}

# Matriz G44: cortes de severidad. Inclusividad de 10% y 25% no está en src/.
CORTES_SEVERIDAD_PCT = (9.9, 10.0, 10.1, 24.9, 25.0, 25.1)

# Matriz G47: ejemplo Fase 3 y cortes THI. Fórmula citada en la matriz, no en src/.
THI_084 = {
    "temperatura_c": 25.0,
    "humedad_pct": 60.0,
    "thi_aprox": 71,
    "clasificacion_esperada": "NORMAL",
}
CORTES_THI = (
    (71.9, "NORMAL"),
    (72.0, "LEVE"),
    (77.9, "LEVE"),
    (78.0, "MODERADO"),
    (83.9, "MODERADO"),
    (84.0, "CRITICO"),
)

# Matriz G48 / G49: combinaciones AND (no se evalúan aquí).
AIRE_105 = (
    {"nh3_ppm": 26, "co2_ppm": 2001, "desviacion_compuesta": True},
    {"nh3_ppm": 26, "co2_ppm": 1999, "desviacion_compuesta": False},
    {"nh3_ppm": 24, "co2_ppm": 2001, "desviacion_compuesta": False},
)
AIRE_085 = {"nh3_ppm": 30, "co2_ppm": 2200, "desviacion_compuesta": True}
HIDRICA_106 = (
    {"ph": 6.0, "o2_mg_l": 4.0, "desviacion_compuesta": True},
    {"ph": 6.0, "o2_mg_l": 6.0, "desviacion_compuesta": False},
    {"ph": 7.0, "o2_mg_l": 4.0, "desviacion_compuesta": False},
)

VENTANA_CORRELACION_NO_RESUELTA = "ficha RF-55.2: Proceso ≤5 s vs Restricciones 30 s"


def localizar_motor_edge() -> Optional[Any]:
    """No hay interfaz oficial de clasificación Edge en este repositorio."""
    return None


def skip_sin_motor_edge(codigo: str, objetivo: str) -> None:
    pytest.skip(
        f"BLOQUEADO {codigo}: no hay motor/simulador Edge en src/ ni tests/. "
        "RecibirEventoEdgeDTO exige clasificacion_rf55 ya calculada. "
        "No se usa POST /iot/eventos-edge como clasificador. "
        f"Objetivo de matriz pendiente: {objetivo}."
    )


def asertar_clasificacion_edge(resultado: dict, esperado: str) -> None:
    assert resultado.get("clasificacion_rf55") == esperado
    assert resultado.get("clasificacion_rf55") in {
        "NORMAL",
        "DESVIACION_SIMPLE",
        "DESVIACION_COMPUESTA",
        "ERROR_CONFIGURACION",
    }

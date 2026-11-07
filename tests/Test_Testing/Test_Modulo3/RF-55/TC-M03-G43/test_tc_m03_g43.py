"""TC-M03-G43 — RF-55.1 / CU-02.

Subcasos: TC-M03-076, TC-M03-077, TC-M03-078.
Clasificación por umbral en el nodo Edge. Recibir un DTO ya clasificado no cubre este grupo.
"""
from __future__ import annotations

import sys
from pathlib import Path

_MODULO3 = Path(__file__).resolve().parents[2]
if str(_MODULO3) not in sys.path:
    sys.path.insert(0, str(_MODULO3))
from rf55_preparacion import skip_sin_motor_edge  # noqa: E402


def test_tc_m03_076_clasificacion_normal_edge() -> None:
    skip_sin_motor_edge(
        "TC-M03-076",
        "valor entre umbral_min y umbral_max → evento NORMAL. "
        "El DTO Dev recibe clasificacion_rf55 ya calculada; no hay umbral_min/max.",
    )


def test_tc_m03_077_sobre_maximo_edge() -> None:
    skip_sin_motor_edge("TC-M03-077", "valor > umbral_max → DESVIACION_SIMPLE")


def test_tc_m03_078_bajo_minimo_edge() -> None:
    skip_sin_motor_edge("TC-M03-078", "valor < umbral_min → DESVIACION_SIMPLE")

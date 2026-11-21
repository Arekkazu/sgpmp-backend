"""TC-M03-G50 — RF-55.2 / CU-02.

Subcasos: TC-M03-086 (>3 variables), TC-M03-107 (<2).
"""
from __future__ import annotations

import sys
from pathlib import Path

_MODULO3 = Path(__file__).resolve().parents[2]
if str(_MODULO3) not in sys.path:
    sys.path.insert(0, str(_MODULO3))
from rf55_preparacion import skip_sin_motor_edge  # noqa: E402


def test_tc_m03_086_cuatro_variables_en_edge() -> None:
    skip_sin_motor_edge(
        "TC-M03-086",
        "regla compuesta con 4 variables → rechazo de configuración",
    )


def test_tc_m03_107_una_variable_en_edge() -> None:
    skip_sin_motor_edge(
        "TC-M03-107",
        "variables_correlacionadas con 1 variable → no evalúa compuesta (E1)",
    )

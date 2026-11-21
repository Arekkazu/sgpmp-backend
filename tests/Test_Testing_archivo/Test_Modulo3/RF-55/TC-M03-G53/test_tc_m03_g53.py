"""TC-M03-G53 — RF-55.2 / CU-02.

Subcasos: TC-M03-109, TC-M03-110.
Referencia de matriz: máx. 5 reglas/ciclo, frecuencia ≥5 s;
RF-55.2 ≤200 ms extra; total con RF-55.1 ≤500 ms.
"""
from __future__ import annotations

import sys
from pathlib import Path

_MODULO3 = Path(__file__).resolve().parents[2]
if str(_MODULO3) not in sys.path:
    sys.path.insert(0, str(_MODULO3))
from rf55_preparacion import (  # noqa: E402
    FRECUENCIA_MIN_S_RF552,
    LATENCIA_MAX_MS_RF55,
    MAX_REGLAS_COMPUESTAS_POR_CICLO,
    PRESUPUESTO_MS_RF552,
    skip_sin_motor_edge,
)


def test_tc_m03_109_limites_ciclo_en_edge() -> None:
    skip_sin_motor_edge(
        "TC-M03-109",
        f"máximo {MAX_REGLAS_COMPUESTAS_POR_CICLO} reglas/ciclo y "
        f"frecuencia mínima ≥{FRECUENCIA_MIN_S_RF552} s",
    )


def test_tc_m03_110_presupuesto_tiempo_en_edge() -> None:
    skip_sin_motor_edge(
        "TC-M03-110",
        f"RF-55.2 ≤{PRESUPUESTO_MS_RF552} ms extra; "
        f"total con RF-55.1 ≤{LATENCIA_MAX_MS_RF55} ms",
    )

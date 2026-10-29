"""TC-M03-G49 — RF-55.2 / CU-02.

Subcaso: TC-M03-106. (pH fuera de 6.5–8.5) AND O2 < 5 mg/L.
Las combinaciones de la matriz no se evalúan aquí: no hay motor de reglas.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_MODULO3 = Path(__file__).resolve().parents[2]
if str(_MODULO3) not in sys.path:
    sys.path.insert(0, str(_MODULO3))
from rf55_preparacion import HIDRICA_106, skip_sin_motor_edge  # noqa: E402


@pytest.mark.parametrize("fila", HIDRICA_106)
def test_tc_m03_106_calidad_hidrica_en_edge(fila: dict) -> None:
    skip_sin_motor_edge(
        "TC-M03-106",
        f"pH={fila['ph']} O2={fila['o2_mg_l']} → "
        f"DESVIACION_COMPUESTA={fila['desviacion_compuesta']}",
    )

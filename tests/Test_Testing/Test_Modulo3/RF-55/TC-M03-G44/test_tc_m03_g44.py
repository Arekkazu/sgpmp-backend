"""TC-M03-G44 — RF-55.1 / CU-02.

Subcasos: TC-M03-079, TC-M03-096.
Cortes 9.9/10/10.1/24.9/25/25.1 %. Inclusividad 10% y 25% no está en src/.
Conservar severidad de un DTO no calcula el porcentaje (eso es RF-56).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_MODULO3 = Path(__file__).resolve().parents[2]
if str(_MODULO3) not in sys.path:
    sys.path.insert(0, str(_MODULO3))
from rf55_preparacion import CORTES_SEVERIDAD_PCT, skip_sin_motor_edge  # noqa: E402


@pytest.mark.parametrize("codigo", ["TC-M03-079", "TC-M03-096"])
def test_cortes_severidad_porcentual_en_edge(codigo: str) -> None:
    skip_sin_motor_edge(
        codigo,
        f"desviaciones {CORTES_SEVERIDAD_PCT} % con umbral_max conocido; "
        "LEVE≤10% / MODERADO 10-25% / CRÍTICO>25%; inclusividad 10 y 25 pendiente de Desarrollo",
    )

"""TC-M03-G47 — RF-55.2 / CU-02.

Subcasos: TC-M03-084, TC-M03-104.
Referencia de matriz (no calculada aquí): T=25°C, HR=60% → THI≈71 NORMAL;
cortes THI 72 / 78 / 84. La fórmula no está en src/telemetry.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_MODULO3 = Path(__file__).resolve().parents[2]
if str(_MODULO3) not in sys.path:
    sys.path.insert(0, str(_MODULO3))
from rf55_preparacion import CORTES_THI, THI_084, skip_sin_motor_edge  # noqa: E402


def test_tc_m03_084_thi_ejemplo_matriz_en_edge() -> None:
    skip_sin_motor_edge(
        "TC-M03-084",
        "referencia matriz: temperatura_c="
        f"{THI_084['temperatura_c']}, humedad_pct={THI_084['humedad_pct']}, "
        f"thi_aprox={THI_084['thi_aprox']} → {THI_084['clasificacion_esperada']} "
        "con regla_aplicada, nombre_regla, version_regla. "
        "No se afirma que Dev calcule THI.",
    )


@pytest.mark.parametrize("thi,esperado", CORTES_THI)
def test_tc_m03_104_cortes_thi_en_edge(thi: float, esperado: str) -> None:
    skip_sin_motor_edge(
        "TC-M03-104",
        f"referencia matriz: THI={thi} → {esperado} "
        "(NORMAL<72; LEVE 72-78; MODERADO 78-84; CRITICO≥84)",
    )

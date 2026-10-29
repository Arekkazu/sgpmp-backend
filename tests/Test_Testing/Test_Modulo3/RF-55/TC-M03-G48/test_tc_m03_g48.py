"""TC-M03-G48 — RF-55.2 / CU-02.

Subcasos: TC-M03-085, TC-M03-105.
AND: NH3>25 ppm y CO2>2000 ppm en la ventana de correlación del nodo.
El Δt≤5 s de ConsolidarEnviarPaqueteUseCase es FA-03 de RF-56, no esta regla.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_MODULO3 = Path(__file__).resolve().parents[2]
if str(_MODULO3) not in sys.path:
    sys.path.insert(0, str(_MODULO3))
from rf55_preparacion import AIRE_085, AIRE_105, skip_sin_motor_edge  # noqa: E402


def test_tc_m03_085_and_calidad_aire_en_edge() -> None:
    skip_sin_motor_edge(
        "TC-M03-085",
        f"referencia matriz: NH3={AIRE_085['nh3_ppm']} ppm y CO2={AIRE_085['co2_ppm']} ppm "
        "en ventana Edge → DESVIACION_COMPUESTA con trazabilidad de regla. "
        "No se usa el Δt de consolidación RF-56 como evidencia.",
    )


@pytest.mark.parametrize("fila", AIRE_105)
def test_tc_m03_105_matriz_and_en_edge(fila: dict) -> None:
    skip_sin_motor_edge(
        "TC-M03-105",
        f"NH3={fila['nh3_ppm']} CO2={fila['co2_ppm']} → "
        f"DESVIACION_COMPUESTA={fila['desviacion_compuesta']}",
    )

"""TC-M03-G37 — RF-55.1 / CU-02.

Subcasos: TC-M03-082 (≤500 ms), TC-M03-102 (ráfaga sin bloqueo).
Rendimiento del nodo Edge. RecibirEventoEdgeDTO no clasifica ni mide latencia.
No se lanza k6/JMeter.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_MODULO3 = Path(__file__).resolve().parents[2]
if str(_MODULO3) not in sys.path:
    sys.path.insert(0, str(_MODULO3))
from rf55_preparacion import LATENCIA_MAX_MS_RF55, skip_sin_motor_edge  # noqa: E402


@pytest.mark.parametrize(
    "codigo,esperado",
    [
        (
            "TC-M03-082",
            f"clasificación de una medición válida en el nodo; tiempo ≤ {LATENCIA_MAX_MS_RF55} ms",
        ),
        (
            "TC-M03-102",
            "captura continua bajo ráfaga: no bloqueo, no pérdida de datos (CA-12)",
        ),
    ],
)
def test_rendimiento_procesamiento_edge(codigo: str, esperado: str) -> None:
    skip_sin_motor_edge(codigo, esperado)

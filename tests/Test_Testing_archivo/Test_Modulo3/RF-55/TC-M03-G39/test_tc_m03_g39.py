"""TC-M03-G39 — RF-55.2 / CU-02.

Subcasos: TC-M03-088 (deshabilitación reiterada), TC-M03-097 (transitorio vs reactivación).
La ausencia de campos rf55_2 en RecibirEventoEdgeDTO no prueba la conmutación del nodo.
"""
from __future__ import annotations

import sys
from pathlib import Path

_MODULO3 = Path(__file__).resolve().parents[2]
if str(_MODULO3) not in sys.path:
    sys.path.insert(0, str(_MODULO3))
from rf55_preparacion import skip_sin_motor_edge  # noqa: E402


def test_tc_m03_088_deshabilitacion_reiterada() -> None:
    skip_sin_motor_edge(
        "TC-M03-088",
        "fallos reiterados deshabilitan RF-55.2 y RF-55.1 sigue operativo. "
        "RecibirEventoEdgeDTO no expone rf55_2/reglas_avanzadas; eso no cubre este CA.",
    )


def test_tc_m03_097_transitorio_y_reactivacion() -> None:
    skip_sin_motor_edge(
        "TC-M03-097",
        "un fallo: fallback puntual; tras umbral: deshabilitar; luego reactivar (E3/E6)",
    )

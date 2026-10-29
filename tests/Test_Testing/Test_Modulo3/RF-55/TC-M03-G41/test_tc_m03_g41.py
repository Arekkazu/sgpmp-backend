"""TC-M03-G41 — RF-55 / CU-02.

Subcaso: TC-M03-101. Configuración de umbrales en caliente en el nodo Edge.
Que el DTO Dev no tenga umbral_min/max no prueba el recarga en caliente.
"""
from __future__ import annotations

import sys
from pathlib import Path

_MODULO3 = Path(__file__).resolve().parents[2]
if str(_MODULO3) not in sys.path:
    sys.path.insert(0, str(_MODULO3))
from rf55_preparacion import skip_sin_motor_edge  # noqa: E402


def test_tc_m03_101_umbrales_en_caliente() -> None:
    skip_sin_motor_edge(
        "TC-M03-101",
        "cambiar umbral_min/max en operación; siguiente medición usa umbrales nuevos "
        "sin reinicio. RecibirEventoEdgeDTO no trae umbrales; eso no cubre este CA.",
    )

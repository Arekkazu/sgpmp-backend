"""TC-M03-G52 — RF-55.2 / CU-02.

Subcaso: TC-M03-108. Ventana de correlación de variables en el nodo.
La ficha contradice Proceso ≤5 s vs Restricciones 30 s. El Δt de RF-56 no cierra este CA.
"""
from __future__ import annotations

import sys
from pathlib import Path

_MODULO3 = Path(__file__).resolve().parents[2]
if str(_MODULO3) not in sys.path:
    sys.path.insert(0, str(_MODULO3))
from rf55_preparacion import VENTANA_CORRELACION_NO_RESUELTA, skip_sin_motor_edge  # noqa: E402


def test_tc_m03_108_limite_correlacion_en_edge() -> None:
    skip_sin_motor_edge(
        "TC-M03-108",
        "justo bajo/sobre el límite oficial: agrupa o descarta (E2). "
        f"Pendiente de decisión: {VENTANA_CORRELACION_NO_RESUELTA}. "
        "No se usa _validar_timestamps de RF-56 como esta regla.",
    )

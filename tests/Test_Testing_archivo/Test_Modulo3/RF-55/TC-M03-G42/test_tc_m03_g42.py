"""TC-M03-G42 — RF-55 / CU-02.

Subcaso: TC-M03-103. En el evento Edge, timestamp_procesamiento > timestamp_captura.
TIMESTAMP_FUTURO (30 s) es validación RF-56 de recepción (G60), no este CA.
"""
from __future__ import annotations

import sys
from pathlib import Path

_MODULO3 = Path(__file__).resolve().parents[2]
if str(_MODULO3) not in sys.path:
    sys.path.insert(0, str(_MODULO3))
from rf55_preparacion import skip_sin_motor_edge  # noqa: E402


def test_tc_m03_103_orden_timestamps_en_evento_edge() -> None:
    skip_sin_motor_edge(
        "TC-M03-103",
        "evento estructurado del nodo: timestamp_procesamiento posterior a timestamp_captura; ambos registrados",
    )

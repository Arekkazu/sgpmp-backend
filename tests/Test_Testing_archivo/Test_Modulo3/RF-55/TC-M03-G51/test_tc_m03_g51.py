"""TC-M03-G51 — RF-55.2 / CU-02.

Subcaso: TC-M03-087. Hardware bajo mínimo: CPU≥160 MHz, RAM≥256 KB, almac.≥1 MB.
"""
from __future__ import annotations

import sys
from pathlib import Path

_MODULO3 = Path(__file__).resolve().parents[2]
if str(_MODULO3) not in sys.path:
    sys.path.insert(0, str(_MODULO3))
from rf55_preparacion import HARDWARE_MIN, skip_sin_motor_edge  # noqa: E402


def test_tc_m03_087_perfil_hardware_en_edge() -> None:
    skip_sin_motor_edge(
        "TC-M03-087",
        f"por debajo de {HARDWARE_MIN} → RF-55.2 off, RF-55.1 operativo",
    )

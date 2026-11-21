"""TC-M03-G54 — RF-55.2 / CU-02.

Subcaso: TC-M03-111. El evento DESVIACION_COMPUESTA generado en Edge incluye
regla_aplicada, nombre_regla y version_regla.
Copiar metadata_edge en RF-56 (G59) no genera esos campos.
"""
from __future__ import annotations

import sys
from pathlib import Path

_MODULO3 = Path(__file__).resolve().parents[2]
if str(_MODULO3) not in sys.path:
    sys.path.insert(0, str(_MODULO3))
from rf55_preparacion import skip_sin_motor_edge  # noqa: E402


def test_tc_m03_111_campos_de_regla_en_evento_edge() -> None:
    skip_sin_motor_edge(
        "TC-M03-111",
        "DESVIACION_COMPUESTA con regla_aplicada, nombre_regla y version_regla emitidos por el nodo",
    )

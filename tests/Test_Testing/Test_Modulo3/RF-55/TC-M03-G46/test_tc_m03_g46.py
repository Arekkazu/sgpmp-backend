"""TC-M03-G46 — RF-55.1 / RF-55.2 / CU-02.

Subcaso: TC-M03-089. Si hay severidad distinta en nivel simple y compuesto,
el evento Edge debe llevar la mayor (LEVE < MODERADO < CRITICO).

Copiar una severidad ya asignada en RF-56 no cubre este cálculo.
"""
from __future__ import annotations

import sys
from pathlib import Path

_MODULO3 = Path(__file__).resolve().parents[2]
if str(_MODULO3) not in sys.path:
    sys.path.insert(0, str(_MODULO3))
from rf55_preparacion import skip_sin_motor_edge  # noqa: E402


def test_tc_m03_089_max_severidad_entre_niveles_edge() -> None:
    skip_sin_motor_edge(
        "TC-M03-089",
        "entrada: severidad RF-55.1 distinta de RF-55.2; "
        "esperado: el evento consolidado en el nodo usa max(LEVE, MODERADO, CRITICO); "
        "falta motor Edge que evalúe ambos niveles",
    )

"""TC-M03-G45 — RF-55.1 / CU-02.

Subcaso: TC-M03-081. Parser Edge: nulo o formato inválido, sin clasificación falsa.
El rechazo Pydantic de valor no numérico en Dev es G58 (DTO), no este parser.
"""
from __future__ import annotations

import sys
from pathlib import Path

_MODULO3 = Path(__file__).resolve().parents[2]
if str(_MODULO3) not in sys.path:
    sys.path.insert(0, str(_MODULO3))
from rf55_preparacion import skip_sin_motor_edge  # noqa: E402


def test_tc_m03_081_parser_edge_dato_invalido() -> None:
    skip_sin_motor_edge(
        "TC-M03-081",
        "valor nulo o malformado en el nodo → log de descarte, sin clasificación falsa",
    )

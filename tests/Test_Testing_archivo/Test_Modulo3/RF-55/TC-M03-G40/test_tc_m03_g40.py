"""TC-M03-G40 — RF-55 / RF-54 / RF-56 / CU-02.

Subcasos: TC-M03-098 buffer local, TC-M03-099 enrutamiento, TC-M03-100 log local.
Persistir estado_conectividad en RF-56 no cubre el buffer ni el log del nodo.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_MODULO3 = Path(__file__).resolve().parents[2]
if str(_MODULO3) not in sys.path:
    sys.path.insert(0, str(_MODULO3))
from rf55_preparacion import skip_sin_motor_edge  # noqa: E402

_ESCENARIOS = (
    (
        "TC-M03-098",
        "estado_conectividad=false → eventos en buffer RF-54, orden cronológico, sin pérdida",
    ),
    (
        "TC-M03-099",
        "estado_conectividad=true → enrutamiento a RF-56 sin buffer intermedio en el nodo",
    ),
    (
        "TC-M03-100",
        "log local del dispositivo con historial reciente (CA-10)",
    ),
)


@pytest.mark.parametrize("codigo,esperado", _ESCENARIOS)
def test_salida_evento_en_nodo(codigo: str, esperado: str) -> None:
    skip_sin_motor_edge(codigo, esperado)

"""TC-M03-G38 — RF-55.1 / CU-02.

Subcasos: TC-M03-083, TC-M03-095, TC-M03-122.
Objetivo: el nodo Edge emite ERROR_CONFIGURACION (umbrales ausentes, cero, severidad).
La recepción RF-56 de un ERROR_CONFIGURACION ya clasificado está en G59, no aquí.
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
        "TC-M03-083",
        {
            "precondicion": "umbral_min y umbral_max no configurados",
            "entrada": "medición válida",
            "esperado": "tipo_evento/clasificacion ERROR_CONFIGURACION; bitácora; no bloquea siguientes",
        },
    ),
    (
        "TC-M03-095",
        {
            "precondicion": "umbral_min=0 o umbral_max=0",
            "entrada": "medición válida",
            "esperado": "ERROR_CONFIGURACION; no división por cero",
        },
    ),
    (
        "TC-M03-122",
        {
            "precondicion": "umbrales ok, parámetros de severidad ausentes",
            "entrada": "medición fuera de rango",
            "esperado": "severidad_invalida; crudo a RF-62; no se inventa ese envío en Dev",
        },
    ),
)


@pytest.mark.parametrize("codigo,escenario", _ESCENARIOS)
def test_error_configuracion_en_edge(codigo: str, escenario: dict) -> None:
    skip_sin_motor_edge(
        codigo,
        f"pre={escenario['precondicion']}; in={escenario['entrada']}; out={escenario['esperado']}",
    )

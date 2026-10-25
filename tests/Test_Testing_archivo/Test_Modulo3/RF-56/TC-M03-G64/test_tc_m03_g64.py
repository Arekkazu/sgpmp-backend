"""TC-M03-G64 — RF-56 / CU-02.

Subcaso: TC-M03-127.
Matriz: ráfaga >> tasa esperada → rate limiting, priorizar críticos, agrupar batch,
sin saturar buffer RF-54 ni el backend.

No hay rate_limit en los routers IoT. Tres execute() en memoria no es carga ni E6.
k6 no se lanza.
"""
from __future__ import annotations

import pytest

_ESCENARIO = {
    "entrada": "ráfaga sostenida de eventos hacia empaquetado/envío, uno o varios dispositivos",
    "esperado": (
        "control de tasa activo; prioridad a eventos críticos; agrupación en batch; "
        "buffer RF-54 y backend sin saturación"
    ),
    "herramienta": "k6 en entorno autorizado, no compartido",
    "falta": (
        "implementación de rate limiting en POST /iot/eventos-edge o en el consolidador; "
        "política de prioridad/batch documentada en código; k6 y umbral de tasa oficial"
    ),
}


def test_tc_m03_127_rafaga_rate_limiting() -> None:
    pytest.skip(
        "BLOQUEADO TC-M03-127: "
        f"entrada={_ESCENARIO['entrada']}. esperado={_ESCENARIO['esperado']}. "
        f"falta={_ESCENARIO['falta']}. herramienta prevista={_ESCENARIO['herramienta']}. "
        "Fuera de alcance: inspect de routers, bucles de use case en memoria, "
        "saturar DEV/TEST, inventar umbral de req/s."
    )

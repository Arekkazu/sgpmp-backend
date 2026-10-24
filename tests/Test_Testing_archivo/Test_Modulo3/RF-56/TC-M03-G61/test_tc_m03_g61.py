"""TC-M03-G61 — RF-56 CA-12 / RF-55 / CU-02.

Subcaso: TC-M03-123.
Requisito: tiempo de detección Edge ≤ 500 ms, medido aislado del empaquetado/envío RF-56.

No hay reloj ni clasificador Edge en este repo. Medir ConsolidarEnviarPaqueteUseCase
o el número de intentos no es el SLA. k6 no se lanza.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_MODULO3 = Path(__file__).resolve().parents[2]
if str(_MODULO3) not in sys.path:
    sys.path.insert(0, str(_MODULO3))
from rf55_preparacion import LATENCIA_MAX_MS_RF55  # noqa: E402

_SLA = {
    "metrica": "tiempo_deteccion_clasificacion_edge_ms",
    "limite": LATENCIA_MAX_MS_RF55,
    "aislamiento": "independiente de construcción y envío del paquete RF-56",
    "entrada": "una medición válida en el nodo Edge",
    "herramienta_prevista": "reloj del simulador Edge; k6 no sustituye el reloj Edge",
}


def test_tc_m03_123_sla_edge_aislado_de_rf56() -> None:
    pytest.skip(
        "BLOQUEADO TC-M03-123: no hay cliente/simulador Edge para medir "
        f"{_SLA['metrica']} ≤ {_SLA['limite']} ms {_SLA['aislamiento']}. "
        "RecibirEventoEdgeUseCase consolida en el mismo execute; un perf_counter "
        "sobre el consolidado no es el SLA. k6 no se ejecuta. "
        f"Preparación prevista: {_SLA['entrada']}; herramienta: {_SLA['herramienta_prevista']}."
    )

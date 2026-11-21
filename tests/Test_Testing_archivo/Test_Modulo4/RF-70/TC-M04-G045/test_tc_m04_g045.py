"""TC-M04-G045 — RF-70.

Subcasos: TC-M04-016, TC-M04-017 (185–186).
Sin canal OTA medible ni TLS de distribución.
"""
from __future__ import annotations

import pytest


def test_tc_m04_016_rendimiento_descarga_activacion() -> None:
    pytest.skip(
        "BLOQUEADO TC-M04-016: no hay descarga de artefacto ni activación en Edge en este repositorio. "
        "No se mide ≤10 min / ≤2 s. Un reloj sobre GET /ota-status no es esa métrica."
    )


def test_tc_m04_017_tls_y_credenciales_canal_ota() -> None:
    pytest.skip(
        "BLOQUEADO TC-M04-017: Motor/OTA Dev no abre socket hacia el nodo. "
        "Validar JWT de GET /prediccion/despliegues no es evidencia de TLS del canal de distribución. "
        "Falta entorno OTA con certificados y Edge."
    )

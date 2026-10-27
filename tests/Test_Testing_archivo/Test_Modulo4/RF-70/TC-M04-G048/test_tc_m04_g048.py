"""TC-M04-G048 — RF-70.

Subcasos: TC-M04-028, TC-M04-030 (191, 193).
BOLA de descarga OTA exige dos dispositivos y un canal de artefactos. No existe.
"""
from __future__ import annotations

import pytest

from src.prediction.infrastructure.routers import ota_router


def test_tc_m04_028_dispositivo_inexistente_o_inactivo() -> None:
    pytest.skip(
        "BLOQUEADO TC-M04-028: no hay POST de distribución ni validación de lista_dispositivos_objetivo. "
        "GET /despliegues no inicia envío; un device_id ausente en consulta no es rechazo de OTA."
    )


def test_tc_m04_030_bola_dispositivo_a_descarga_b() -> None:
    pytest.skip(
        "BLOQUEADO TC-M04-030: no hay endpoint de descarga de paquete OTA autenticado por device_id. "
        "Un DTO inválido o un GET sin filas no es BOLA. Faltan dos identidades de dispositivo de prueba "
        "y el servicio IoT/IA que entrega el artefacto."
    )


def test_tc_m04_028_030_sin_ruta_de_descarga() -> None:
    paths = [getattr(r, "path", "") for r in ota_router.router.routes]
    assert all("download" not in p.lower() and "artefacto" not in p.lower() for p in paths)
    assert "/prediccion/despliegues" in "".join(paths) or any("despliegues" in p for p in paths)

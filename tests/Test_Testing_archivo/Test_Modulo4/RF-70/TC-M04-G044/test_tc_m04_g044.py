"""TC-M04-G044 — RF-70.

Subcasos: TC-M04-012 a TC-M04-015 (181–184).
Dev no implementa descarga fragmentada, reanudación, hash en tránsito ni rollback de activación.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from src.prediction.domain.repositories.despliegue_ota_repository import DespliegueOtaRepository

_MOD4 = Path(__file__).resolve().parents[2]
if str(_MOD4) not in sys.path:
    sys.path.insert(0, str(_MOD4))
from rf70_dobles import DespliegueRepoMemoria, despliegue  # noqa: E402


def test_tc_m04_012_reanudacion_fragmentos() -> None:
    pytest.skip(
        "BLOQUEADO TC-M04-012: no hay servicio de descarga fragmentada ni cursor de último fragmento. "
        "DespliegueOtaRepository solo consulta (obtener_por_version, listar, obtener_por_id)."
    )


def test_tc_m04_013_hash_y_rollback() -> None:
    pytest.skip(
        "BLOQUEADO TC-M04-013: el hash_modelo_sha256 se almacena en el registro de consulta; "
        "nadie calcula SHA-256 del artefacto ni ejecuta rollback ante mismatch en este repo."
    )


def test_tc_m04_014_rollback_activacion() -> None:
    pytest.skip(
        "BLOQUEADO TC-M04-014: rollback_ejecutado es un campo de lectura en DespliegueOta; "
        "no hay use case que restaure la versión anterior en ≤2 s."
    )


def test_tc_m04_015_condiciones_dispositivo() -> None:
    pytest.skip(
        "BLOQUEADO TC-M04-015: batería, almacenamiento y ventana OTA no se validan en Dev. "
        "Los campos existen en la entidad de consulta; IoT/IA escribe la tabla."
    )


def test_tc_m04_012_015_puerto_sin_escritura_ota() -> None:
    nombres = {n for n, _ in DespliegueOtaRepository.__dict__.items() if not n.startswith("_")}
    assert "guardar" not in nombres
    assert "iniciar" not in nombres
    d = despliegue(estado_despliegue="FALLIDO", motivo_fallo="HASH_INVALIDO", rollback_ejecutado=True)
    repo = DespliegueRepoMemoria([d])
    leido = repo.obtener_por_id(1)
    assert leido.estado_despliegue == "FALLIDO"
    assert leido.rollback_ejecutado is True
    assert leido.motivo_fallo == "HASH_INVALIDO"

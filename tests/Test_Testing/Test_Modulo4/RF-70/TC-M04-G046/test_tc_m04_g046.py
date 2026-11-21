"""TC-M04-G046 — RF-70.

Subcasos: TC-M04-018, TC-M04-027 (187, 190).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from src.prediction.application.use_cases.ota.listar_despliegues_use_case import ListarDesplieguesUseCase

_MOD4 = Path(__file__).resolve().parents[2]
if str(_MOD4) not in sys.path:
    sys.path.insert(0, str(_MOD4))
from rf70_dobles import (  # noqa: E402
    AuditoriaMemoria,
    DespliegueRepoMemoria,
    SesionNula,
    VersionPortOta,
    despliegue,
)


def test_tc_m04_018_concurrencia_un_proceso_por_dispositivo() -> None:
    pytest.skip(
        "BLOQUEADO TC-M04-018: no hay endpoint de inicio OTA ni lock por dispositivo. "
        "Dos GET concurrentes no demuestran exclusión de procesos de distribución."
    )


def test_tc_m04_027_modos_inmediato_programado_lotes() -> None:
    pytest.skip(
        "BLOQUEADO TC-M04-027: modo_distribucion se lee del registro; Dev no orquesta "
        "INMEDIATO/PROGRAMADO/POR_LOTES ni secuencia subconjuntos."
    )


def test_tc_m04_027_consulta_filtra_por_dispositivo() -> None:
    """Aislamiento de consulta entre dispositivos; no es orquestación OTA."""
    repo = DespliegueRepoMemoria(
        [
            despliegue(id_despliegue_ota=1, id_dispositivo_iot=10, modo_distribucion="INMEDIATO"),
            despliegue(id_despliegue_ota=2, id_dispositivo_iot=11, modo_distribucion="PROGRAMADO"),
        ]
    )
    uc = ListarDesplieguesUseCase(
        db=SesionNula(),
        repo=repo,
        auditoria_repo=AuditoriaMemoria(),
        version_port=VersionPortOta(),
    )
    items, total = uc.execute(
        id_version=3, id_dispositivo=10, estado=None, limit=20, offset=0, id_usuario=1
    )
    assert total == 1
    assert items[0].id_dispositivo_iot == 10
    assert items[0].modo_distribucion == "INMEDIATO"

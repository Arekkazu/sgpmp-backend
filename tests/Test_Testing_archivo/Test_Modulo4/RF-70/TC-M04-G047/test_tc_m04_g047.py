"""TC-M04-G047 — RF-70.

Subcasos: TC-M04-025, TC-M04-026, TC-M04-029 (188, 189, 192).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from src.prediction.application.use_cases.ota.consultar_ota_status_use_case import (
    ConsultarOtaStatusUseCase,
)
from src.shared.errors import NotFoundError, ValidationError

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


def _consultar(repo, versiones=None):
    return ConsultarOtaStatusUseCase(
        db=SesionNula(),
        repo=repo,
        auditoria_repo=AuditoriaMemoria(),
        version_port=versiones or VersionPortOta(),
    )


def test_tc_m04_025_consulta_estado_por_version_en_memoria() -> None:
    """Consulta Dev de registros ya persistidos. No es el panel M09 ni tiempo real."""
    repo = DespliegueRepoMemoria(
        [
            despliegue(id_despliegue_ota=1, estado_despliegue="EXITOSO"),
            despliegue(id_despliegue_ota=2, id_dispositivo_iot=17, estado_despliegue="FALLIDO", motivo_fallo="RED"),
        ]
    )
    uc = _consultar(repo)
    id_v, items = uc.execute(id_version=3, id_dispositivo=None, estado=None, id_usuario=4)
    assert id_v == 3
    assert len(items) == 2
    assert {d.estado_despliegue for d in items} == {"EXITOSO", "FALLIDO"}


def test_tc_m04_025_consulta_m09_tiempo_real() -> None:
    pytest.skip(
        "BLOQUEADO TC-M04-025 (M09): no se invoca API de M09 ni se verifica reflejo en tiempo real. "
        "GET /prediccion/modelos/{id}/ota-status es lectura M04 sobre despliegues_ota."
    )


def test_tc_m04_026_filtro_sin_cambios_no_es_omision_de_transferencia() -> None:
    repo = DespliegueRepoMemoria(
        [despliegue(id_despliegue_ota=9, estado_despliegue="SIN_CAMBIOS", tamano_descargado_bytes=0)]
    )
    uc = _consultar(repo)
    _, items = uc.execute(id_version=3, id_dispositivo=None, estado="SIN_CAMBIOS", id_usuario=1)
    assert len(items) == 1
    assert items[0].estado_despliegue == "SIN_CAMBIOS"


def test_tc_m04_026_omitir_transferencia_si_ya_tiene_version() -> None:
    pytest.skip(
        "BLOQUEADO TC-M04-026 (idempotencia OTA): filtrar SIN_CAMBIOS no demuestra que se omitió "
        "la transferencia al solicitar distribución hacia un dispositivo que ya tiene la versión."
    )


def test_tc_m04_026_estado_filtro_invalido() -> None:
    uc = _consultar(DespliegueRepoMemoria())
    with pytest.raises(ValidationError) as exc:
        uc.execute(id_version=3, id_dispositivo=None, estado="HECHO", id_usuario=1)
    assert exc.value.code == "ESTADO_INVALIDO"


def test_tc_m04_029_resiliencia_reporte_y_persistencia() -> None:
    pytest.skip(
        "BLOQUEADO TC-M04-029: no hay recepción de reporte del nodo ni reintento de persistencia. "
        "ConsultarOtaStatusUseCase hace rollback solo si falla registrar auditoría de la consulta."
    )


def test_tc_m04_025_version_inexistente() -> None:
    uc = _consultar(DespliegueRepoMemoria(), VersionPortOta({}))
    with pytest.raises(NotFoundError) as exc:
        uc.execute(id_version=99, id_dispositivo=None, estado=None, id_usuario=1)
    assert exc.value.code == "VERSION_NO_ENCONTRADA"

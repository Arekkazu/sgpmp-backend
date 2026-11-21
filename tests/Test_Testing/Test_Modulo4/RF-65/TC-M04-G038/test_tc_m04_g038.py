"""TC-M04-G038 — RF-65 / CU-02.

Subcasos: TC-M04-005, TC-M04-021.
Gate de versión: PreconditionFailedError MODELO_NO_ACTIVO (HTTP 412).
Incompatibilidad de llave: BusinessRuleError VERSION_MODELO_INCOMPATIBLE (HTTP 422).
La matriz pide HTTP 409 para el segundo; el contrato Dev mapea BusinessRuleError a 422.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from src.shared.errors import BusinessRuleError, PreconditionFailedError

_MOD4 = Path(__file__).resolve().parents[2]
if str(_MOD4) not in sys.path:
    sys.path.insert(0, str(_MOD4))
from rf65_dobles import VersionPortFijo, dto_motor, ensamblar  # noqa: E402


@pytest.mark.parametrize("estado", ["APROBADO", "DEPRECADO", "RECHAZADO"])
def test_tc_m04_005_rechaza_modelo_no_activo(estado: str) -> None:
    uc, repo, auditoria, _, _, _ = ensamblar(
        versiones=VersionPortFijo({40: (estado, "MODELO_ESPECIES_GRANDES", None)})
    )
    uc.execute(dto_motor(), id_usuario=1)
    with pytest.raises(PreconditionFailedError) as exc:
        uc.execute(dto_motor(id_version_modelo_activa=40), id_usuario=1)
    assert exc.value.code == "MODELO_NO_ACTIVO"
    assert exc.value.status_code == 412
    vigente = repo.obtener_por_tipo("MODELO_ESPECIES_GRANDES")
    assert vigente.id_version_modelo_activa is None
    assert vigente.config_version == 1
    assert len(auditoria.eventos) == 1


def test_tc_m04_005_acepta_modelo_activo() -> None:
    uc, repo, _, _, _, _ = ensamblar(
        versiones=VersionPortFijo({20: ("ACTIVO", "MODELO_ESPECIES_GRANDES", None)})
    )
    entidad, _ = uc.execute(dto_motor(id_version_modelo_activa=20), id_usuario=1)
    assert entidad.id_version_modelo_activa == 20
    assert repo.obtener_por_tipo(entidad.tipo_modelo).id_version_modelo_activa == 20


def test_tc_m04_021_incompatibilidad_es_422_no_409() -> None:
    """Conflicto matriz vs implementación: se espera 409; Dev lanza 422."""
    uc, repo, _, _, _, _ = ensamblar(
        versiones=VersionPortFijo({20: ("ACTIVO", "MODELO_AVES", "DETECTOR")})
    )
    uc.execute(dto_motor(), id_usuario=1)
    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(dto_motor(id_version_modelo_activa=20), id_usuario=1)
    assert exc.value.code == "VERSION_MODELO_INCOMPATIBLE"
    assert exc.value.status_code == 422
    assert exc.value.status_code != 409
    vigente = repo.obtener_por_tipo("MODELO_ESPECIES_GRANDES")
    assert vigente.id_version_modelo_activa is None
    assert vigente.config_version == 1

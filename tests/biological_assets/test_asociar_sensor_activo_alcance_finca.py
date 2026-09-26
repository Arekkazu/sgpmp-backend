"""INC-M02-37-G87 v2.0: el permiso CREATE de RF-49 no debe abrir BOLA.

Al habilitar al Productor, el activo solicitado debe resolverse dentro de las
fincas que le pertenecen. Un activo ajeno se enmascara con el mismo contrato
422 usado para un activo inexistente.
"""
from __future__ import annotations

import pytest

from src.biological_assets.application.use_cases.gestion.asociar_sensor_activo_use_case import (
    AsociarSensorActivoUseCase,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError


class ActivoRepoFake:
    def __init__(self, activo: object) -> None:
        self.activo = activo
        self.alcance_recibido: list[int] | None = None

    def obtener_por_id(self, _id: int, *, ids_fincas_permitidas=None):
        self.alcance_recibido = ids_fincas_permitidas
        if ids_fincas_permitidas is not None:
            return None
        return self.activo


def _use_case(activo_repo: ActivoRepoFake) -> AsociarSensorActivoUseCase:
    return AsociarSensorActivoUseCase(
        db=None,
        repo=None,
        activo_repo=activo_repo,
        sensor_port=None,
        infra_port=None,
    )


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=7, id_token=1, id_rol=2)


def test_rechaza_activo_fuera_del_alcance_antes_de_consultar_sensor():
    repo = ActivoRepoFake(activo=object())

    with pytest.raises(BusinessRuleError) as exc:
        _use_case(repo).execute(
            99,
            dto=None,
            usuario_actual=_usuario(),
            ids_fincas_permitidas=[10],
        )

    assert exc.value.code == 'ACTIVO_NO_ENCONTRADO'
    assert repo.alcance_recibido == [10]


def test_alcance_global_conserva_acceso_al_activo():
    repo = ActivoRepoFake(activo=object())

    # El activo pasa V1; se detiene en V2 porque el objeto mínimo no tiene
    # estado. El foco es comprobar que alcance global (None) no lo filtre.
    with pytest.raises(AttributeError):
        _use_case(repo).execute(
            99,
            dto=None,
            usuario_actual=_usuario(),
            ids_fincas_permitidas=None,
        )

    assert repo.alcance_recibido is None

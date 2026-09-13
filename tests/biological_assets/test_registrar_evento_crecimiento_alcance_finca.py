"""INC-M02-71-G48 (RF-40): execute() resolvia el activo con
obtener_por_id(id_activo), sin ids_fincas_permitidas -- a diferencia de las
rutas de consulta del mismo modulo, que si lo aplican. Un usuario con permiso
de creacion podia potencialmente registrar un evento de crecimiento sobre un
activo de una finca fuera de su alcance.
"""
from __future__ import annotations

import pytest

from src.biological_assets.application.use_cases.gestion.registrar_evento_crecimiento_use_case import (
    RegistrarEventoCrecimientoUseCase,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError


class ActivoRepoFake:
    """Simula el filtrado real: fuera de alcance -> None, igual que el repository SQL."""

    def __init__(self, activo) -> None:
        self.activo = activo

    def obtener_por_id(self, _id: int, *, ids_fincas_permitidas=None):
        if ids_fincas_permitidas is not None:
            return None
        return self.activo


def _use_case(activo_repo):
    return RegistrarEventoCrecimientoUseCase(
        db=None, activo_repo=activo_repo, evento_repo=None,
        infra_port=None, parametros_port=None, ciclo_port=None,
    )


def test_rechaza_activo_fuera_del_alcance_de_finca():
    uc = _use_case(ActivoRepoFake(activo=object()))
    usuario = UsuarioActual(id_usuario=1, id_token=1, id_rol=2)

    with pytest.raises(NotFoundError) as exc:
        uc.execute(99, dto=None, usuario=usuario, ids_fincas_permitidas=[10])

    assert exc.value.code == 'ACTIVO_NO_ENCONTRADO'


def test_alcance_global_no_filtra():
    activo = object()
    uc = _use_case(ActivoRepoFake(activo=activo))
    usuario = UsuarioActual(id_usuario=1, id_token=1, id_rol=1)

    # ids_fincas_permitidas=None (alcance global, ej. Administrador) no filtra
    # -- se detiene mas adelante por falta de dependencias reales, no es el
    # foco de este test (solo nos interesa que obtener_por_id reciba el activo).
    with pytest.raises(AttributeError):
        uc.execute(99, dto=None, usuario=usuario, ids_fincas_permitidas=None)

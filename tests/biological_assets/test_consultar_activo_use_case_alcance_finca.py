"""INC-M02-39-G27 / issue #199 (RF-36): QA reportó que GET
/activos-biologicos/{id_activo} no filtraba por finca -- un Productor de la
Finca 1 podía consultar (200 OK) un lote de la Finca 2 completo (especie,
cantidad, costo de adquisición, soporte documental), un BOLA (OWASP API1:2023).

Verificado contra `dev` actual: el fix ya existe -- commit `6ca29b5a`
("feat(rf25): restringir activos biológicos a la finca del usuario") ya
propaga `ids_fincas_permitidas` desde el router hasta
`ActivoBiologicoRepository.obtener_por_id`, que devuelve `None` (no un error
que distinga "existe pero no es tuyo") cuando la infraestructura del activo
no pertenece a una finca del alcance del usuario -- el use case lo traduce a
`404 ACTIVO_NO_ENCONTRADO`, evitando la fuga de información que señaló QA.
El reporte de QA corrió contra `sgpmp_test`, una revisión anterior a este
commit. Este test fija el comportamiento correcto para que no vuelva a
regresar.
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.biological_assets.application.use_cases.gestion.consultar_activo_use_case import (
    ConsultarActivoUseCase,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError


@dataclass
class _ActivoFake:
    tipo: str = 'POBLACIONAL'


class ActivoRepoFake:
    """Simula el filtrado real del repository SQL: el activo pertenece a
    `id_finca_del_activo`, y solo se devuelve si esa finca está dentro de
    `ids_fincas_permitidas` (o si el alcance es global, `None`)."""

    def __init__(self, activo, id_finca_del_activo: int = 2) -> None:
        self.activo = activo
        self.id_finca_del_activo = id_finca_del_activo

    def obtener_por_id(self, _id: int, *, ids_fincas_permitidas=None):
        if ids_fincas_permitidas is not None and self.id_finca_del_activo not in ids_fincas_permitidas:
            return None
        return self.activo


def _use_case(activo_repo):
    return ConsultarActivoUseCase(db=None, repo=activo_repo, bitacora_repo=None)


def test_lote_de_otra_finca_responde_404_no_200():
    """Caso reportado: Productor de Finca 1 consulta el lote 8, de Finca 2."""
    uc = _use_case(ActivoRepoFake(activo=_ActivoFake(), id_finca_del_activo=2))
    usuario = UsuarioActual(id_usuario=35, id_token=1, id_rol=2)

    with pytest.raises(NotFoundError) as exc:
        uc.execute(8, usuario, ids_fincas_permitidas=[1])

    assert exc.value.code == 'ACTIVO_NO_ENCONTRADO'


def test_lote_de_la_propia_finca_se_consulta_normalmente():
    activo = _ActivoFake()
    uc = _use_case(ActivoRepoFake(activo=activo, id_finca_del_activo=1))
    usuario = UsuarioActual(id_usuario=35, id_token=1, id_rol=2)

    resultado = uc.execute(8, usuario, ids_fincas_permitidas=[1, 2])

    assert resultado is activo


def test_alcance_global_no_filtra():
    """Un rol con alcance global (ej. Administrador) recibe
    ids_fincas_permitidas=None y no se filtra por finca."""
    activo = _ActivoFake()
    uc = _use_case(ActivoRepoFake(activo=activo, id_finca_del_activo=999))
    usuario = UsuarioActual(id_usuario=1, id_token=1, id_rol=1)

    resultado = uc.execute(8, usuario, ids_fincas_permitidas=None)

    assert resultado is activo

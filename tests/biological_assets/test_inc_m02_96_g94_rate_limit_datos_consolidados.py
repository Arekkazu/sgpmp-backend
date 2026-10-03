"""INC-M02-96-G94 — GET /{id_activo}/datos-consolidados no aplicaba ningun
limitador de tasa (RF-50 exige 100 solicitudes/minuto). Verifica que el
limitador esta realmente conectado a la ruta y que corta con 429 al superar
el limite configurado, en el mismo estilo que
tests/shared/test_inc_m09_21_g125_02_rate_limit.py.

RF-50: el limite es por modulo consumidor -- las identidades tecnicas de un
mismo modulo ('Integración M0<n>') comparten contador; los usuarios humanos
conservan uno propio cada uno.
"""
from __future__ import annotations

import pytest

from src.biological_assets.infrastructure.routers import activo_biologico_router as modulo_router
from src.biological_assets.infrastructure.routers.activo_biologico_router import (
    _LIMITE_DATOS_CONSOLIDADOS,
    _clave_consumidor_datos_consolidados,
    router,
)
from src.identity_access.domain.entities.rol import Rol
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import TooManyRequestsError

_ROLES = {
    2: Rol(nombre_rol='Productor', es_protegido=False, id_rol=2),
    12: Rol(nombre_rol='Integración M04', es_protegido=False, id_rol=12),
    15: Rol(nombre_rol='Integración M06', es_protegido=False, id_rol=15),
}


class _RolRepoFake:
    def __init__(self, _db) -> None:
        pass

    def obtener_por_id(self, id_rol: int):
        return _ROLES.get(id_rol)


@pytest.fixture(autouse=True)
def _roles_fake(monkeypatch):
    monkeypatch.setattr(modulo_router, 'SqlAlchemyRolRepository', _RolRepoFake)


def _clave(id_usuario: int, id_rol: int) -> str:
    return _clave_consumidor_datos_consolidados(
        db=None, usuario_actual=UsuarioActual(id_usuario=id_usuario, id_token=1, id_rol=id_rol),
    )


def _llamar(id_usuario: int, id_rol: int) -> None:
    _LIMITE_DATOS_CONSOLIDADOS(request=None, identificador=_clave(id_usuario, id_rol))


def test_ruta_datos_consolidados_declara_el_limitador() -> None:
    ruta = next(
        r for r in router.routes
        if getattr(r, "path", None) == "/activos-biologicos/{id_activo}/datos-consolidados"
    )
    dependencias = {d.call for d in ruta.dependant.dependencies}
    assert _LIMITE_DATOS_CONSOLIDADOS in dependencias
    limitador = next(d for d in ruta.dependant.dependencies if d.call is _LIMITE_DATOS_CONSOLIDADOS)
    assert _clave_consumidor_datos_consolidados in {d.call for d in limitador.dependencies}
    assert 429 in ruta.responses


def test_limitador_corta_tras_100_solicitudes_por_minuto() -> None:
    for _ in range(100):
        _llamar(9001, 2)

    with pytest.raises(TooManyRequestsError) as exc:
        _llamar(9001, 2)
    assert exc.value.code == "LIMITE_TASA_EXCEDIDO"
    assert exc.value.status_code == 429


def test_clave_humano_es_por_usuario() -> None:
    assert _clave(7, 2) == 'usuario:7'
    assert _clave(8, 2) == 'usuario:8'


def test_clave_identidad_tecnica_es_por_modulo() -> None:
    assert _clave(50, 12) == 'modulo:modulo4'
    assert _clave(51, 12) == 'modulo:modulo4'
    assert _clave(60, 15) == 'modulo:modulo6'


def test_usuarios_de_un_mismo_modulo_comparten_el_limite() -> None:
    for i in range(100):
        _llamar(9100 + i % 2, 12)  # dos usuarios tecnicos de M04 alternados

    with pytest.raises(TooManyRequestsError):
        _llamar(9102, 12)
    # Otro modulo y los humanos no se ven afectados por el consumo de M04.
    _llamar(9200, 15)
    _llamar(9300, 2)


def test_usuarios_humanos_no_comparten_el_limite() -> None:
    for _ in range(100):
        _llamar(9400, 2)

    with pytest.raises(TooManyRequestsError):
        _llamar(9400, 2)
    _llamar(9401, 2)

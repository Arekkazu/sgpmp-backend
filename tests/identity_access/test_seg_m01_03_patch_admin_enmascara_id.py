"""SEG-M01-03 (#439): PATCH /usuarios/{id} solo devuelve el ID completo con el permiso E."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src.identity_access.infrastructure.routers import usuarios_routers as r

_NUMERO = '1234567890'


@pytest.fixture
def editar(monkeypatch):
    usuario = SimpleNamespace(
        id_usuario=7, nombre='Ana', apellidos='Ruiz', correo='ana@ejemplo.com',
        tipo_identificacion='CC', numero_identificacion=_NUMERO, genero=None, id_rol=2,
        fecha_registro=datetime.now(timezone.utc), telefono=None, direccion=None, version=2,
    )
    monkeypatch.setattr(
        r, '_crear_editar_perfil_use_case',
        lambda db: SimpleNamespace(execute=lambda *a: usuario),
    )
    actor = SimpleNamespace(id_usuario=1, id_rol=9)

    def _editar(permiso=None, falla=False, ruta=r.editar_perfil_admin):
        def buscar(**kwargs):
            assert kwargs == {'id_rol': 9, 'id_recurso': 1, 'id_accion': 5}
            if falla:
                raise RuntimeError('BD caída')
            return permiso
        monkeypatch.setattr(r, 'SqlAlchemyPermisoRepository', lambda db: SimpleNamespace(buscar=buscar))
        if ruta is r.editar_perfil_propio:
            return ruta(dto=None, db=None, usuario_actual=actor)
        return ruta(id_usuario=7, dto=None, db=None, usuario_actual=actor)

    return _editar


def test_sin_permiso_ejecutar_se_enmascara(editar):
    assert editar(permiso=None).numero_identificacion == '1234******'


def test_permiso_ejecutar_inactivo_se_enmascara(editar):
    assert editar(permiso=SimpleNamespace(es_activo=False)).numero_identificacion == '1234******'


def test_fallo_al_resolver_permiso_enmascara(editar):
    assert editar(falla=True).numero_identificacion == '1234******'


def test_con_permiso_ejecutar_ve_el_numero_completo(editar):
    assert editar(permiso=SimpleNamespace(es_activo=True)).numero_identificacion == _NUMERO


def test_patch_me_no_cambia(editar):
    assert editar(permiso=None, ruta=r.editar_perfil_propio).numero_identificacion == _NUMERO

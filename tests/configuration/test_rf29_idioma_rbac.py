"""RF-29 — compuerta RBAC de los endpoints de idioma (recursos 26 y 27).

El FA "Privilegios insuficientes (Configuración Global)" pide que un rol no
administrador que intente cambiar el idioma predeterminado de la plataforma
reciba un 403 con un mensaje propio, no el `ACCESO_DENEGADO` genérico que
`require_permission` devuelve en el resto del sistema.

Se prueba a nivel de router con `TestClient` y sin base de datos: la matriz de
`modulo1.permisos` se sustituye por un fake, así que lo que se verifica es la
compuerta y el mensaje, no la query. La matriz real está documentada en
`anotaciones/modulo_9/cu06_gaps_bd_rf25_rf29.md` (recurso 26 → roles 1-5 con
R/U; recurso 27 → solo Administrador con R/U) y es la que replica
`PERMISOS_REALES` de abajo.
"""
from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.configuration.infrastructure.routers.preferencia_idioma_router import router
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers

ADMIN = UsuarioActual(id_usuario=1, id_token=1, id_rol=1, id_estado_cuenta=2)
PRODUCTOR = UsuarioActual(id_usuario=7, id_token=1, id_rol=2, id_estado_cuenta=2)
CUENTA_PENDIENTE = UsuarioActual(id_usuario=8, id_token=1, id_rol=1, id_estado_cuenta=1)

# (id_rol, id_recurso, id_accion) activos, copiados de modulo1.permisos.
PERMISOS_REALES = {(rol, 26, accion) for rol in (1, 2, 3, 4, 5) for accion in (2, 3)} | {
    (1, 27, 2),
    (1, 27, 3),
}


class _Query:
    """Reproduce `db.query(Permisos).filter(...).first()` sobre la matriz fake."""

    def __init__(self, usuario: UsuarioActual) -> None:
        self.usuario = usuario
        self.criterios: list = []

    def filter(self, *criterios):
        self.criterios.extend(criterios)
        return self

    def first(self):
        # require_permission filtra por id_rol, id_recurso, id_accion y es_activo.
        # Solo los tres primeros llevan un literal entero al lado derecho; el
        # `es_activo.is_(True)` no tiene `.right.value`, por eso se descarta.
        valores = [
            c.right.value
            for c in self.criterios
            if getattr(getattr(c, "right", None), "value", None) is not None
        ]
        _rol, recurso, accion = valores[-3:]
        clave = (self.usuario.id_rol, recurso, accion)
        return object() if clave in PERMISOS_REALES else None


class DbFake:
    def __init__(self, usuario: UsuarioActual) -> None:
        self.usuario = usuario

    def query(self, *_args):
        return _Query(self.usuario)


def _client(usuario: UsuarioActual | None) -> Generator[TestClient, None, None]:
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)

    if usuario is not None:
        app.dependency_overrides[get_current_user] = lambda: usuario
        app.dependency_overrides[get_db] = lambda: DbFake(usuario)

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def cliente_productor() -> Generator[TestClient, None, None]:
    yield from _client(PRODUCTOR)


@pytest.fixture
def cliente_admin() -> Generator[TestClient, None, None]:
    yield from _client(ADMIN)


@pytest.fixture
def cliente_anonimo() -> Generator[TestClient, None, None]:
    yield from _client(None)


def test_sin_token_es_401(cliente_anonimo: TestClient) -> None:
    respuesta = cliente_anonimo.get("/configuracion/personalizacion/idioma")
    assert respuesta.status_code == 401


def test_productor_lee_su_propia_preferencia(cliente_productor: TestClient) -> None:
    """El recurso 26 lo leen todos los roles: la compuerta no debe bloquear."""
    respuesta = cliente_productor.get("/configuracion/personalizacion/idioma")
    assert respuesta.status_code not in (401, 403)


def test_productor_en_el_patch_global_es_403_con_el_mensaje_del_rf(
    cliente_productor: TestClient,
) -> None:
    respuesta = cliente_productor.patch(
        "/configuracion/personalizacion/idioma/global",
        json={"locale_code": "en-US"},
    )
    cuerpo = respuesta.json()

    assert respuesta.status_code == 403
    assert cuerpo["error_code"] == "ACCESO_DENEGADO"
    assert cuerpo["message"] == (
        "Acceso denegado: Solo el Administrador del sistema puede definir el "
        "idioma predeterminado global de la plataforma."
    )


def test_productor_en_el_get_global_es_403_con_el_mismo_mensaje(
    cliente_productor: TestClient,
) -> None:
    respuesta = cliente_productor.get("/configuracion/personalizacion/idioma/global")
    assert respuesta.status_code == 403
    assert "Solo el Administrador del sistema" in respuesta.json()["message"]


def test_admin_pasa_la_compuerta_del_global(cliente_admin: TestClient) -> None:
    respuesta = cliente_admin.patch(
        "/configuracion/personalizacion/idioma/global",
        json={"locale_code": "en-US"},
    )
    assert respuesta.status_code not in (401, 403)


def test_el_403_de_idioma_personal_conserva_el_mensaje_generico() -> None:
    """El mensaje propio es solo del global; el resto del sistema no cambia."""
    sin_permisos = UsuarioActual(id_usuario=9, id_token=1, id_rol=99, id_estado_cuenta=2)
    gen = _client(sin_permisos)
    cliente = next(gen)

    respuesta = cliente.patch(
        "/configuracion/personalizacion/idioma",
        json={"locale_code": "en-US"},
    )

    assert respuesta.status_code == 403
    assert respuesta.json()["message"] == (
        "Acceso denegado. Su rol no tiene permisos para realizar esta operación."
    )


def test_cuenta_no_activa_no_pasa_la_compuerta() -> None:
    """RF-04: los permisos solo son efectivos con la cuenta activa."""
    gen = _client(CUENTA_PENDIENTE)
    cliente = next(gen)

    respuesta = cliente.get("/configuracion/personalizacion/idioma")

    assert respuesta.status_code == 403
    assert respuesta.json()["error_code"] == "CUENTA_NO_ACTIVA"

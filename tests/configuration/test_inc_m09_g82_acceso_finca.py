"""Regresión INC-M09-G82: una lectura RBAC no concede acceso global a fincas."""
from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.configuration.domain.entities.finca import Finca
from src.configuration.domain.value_objects.nombre_finca import NombreFinca
from src.configuration.domain.value_objects.tamano_h import TamanoH
from src.configuration.domain.value_objects.ubicacion_finca import UbicacionFinca
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers


RECURSO_FINCAS = 9
ACCION_LEER = 2
ACCION_ACTUALIZAR = 3

LECTOR_SIN_FINCA = UsuarioActual(
    id_usuario=400,
    id_token=1,
    id_rol=47,
    id_estado_cuenta=2,
)
LECTOR_ASIGNADO = UsuarioActual(
    id_usuario=401,
    id_token=2,
    id_rol=48,
    id_estado_cuenta=2,
)
GESTOR_GLOBAL = UsuarioActual(
    id_usuario=900,
    id_token=3,
    id_rol=91,
    id_estado_cuenta=2,
)


def _finca(id_finca: int, nombre: str, id_usuario: int | None) -> Finca:
    ahora = datetime(2026, 9, 7, tzinfo=timezone.utc)
    return Finca(
        id_finca=id_finca,
        nombre=NombreFinca(nombre),
        ubicacion=UbicacionFinca(
            departamento="Huila",
            municipio="Neiva",
            vereda="Centro",
            latitud=Decimal("2.93"),
            longitud=Decimal("-75.28"),
        ),
        tamano_h=TamanoH(Decimal("12.5")),
        es_activo=True,
        fecha_creacion=ahora,
        fecha_actualizacion=ahora,
        id_usuario=id_usuario,
    )


FINCA_AJENA = _finca(19, "Finca Ajena", 200)
FINCA_PROPIA = _finca(20, "Finca Propia", LECTOR_ASIGNADO.id_usuario)


class FincaRepoFake:
    def __init__(self, fincas: list[Finca]) -> None:
        self.fincas = fincas

    def obtener_por_id(self, id_finca: int) -> Finca | None:
        return next((finca for finca in self.fincas if finca.id_finca == id_finca), None)

    def listar(
        self,
        *,
        id_usuario_filtro: int | None = None,
        solo_activas: bool = False,
    ) -> list[Finca]:
        return [
            finca
            for finca in self.fincas
            if (id_usuario_filtro is None or finca.id_usuario == id_usuario_filtro)
            and (not solo_activas or finca.es_activo)
        ]


class _QueryPermisoFake:
    def __init__(self, permisos: set[tuple[int, int, int]]) -> None:
        self.permisos = permisos
        self.criterios: list = []

    def filter(self, *criterios):
        self.criterios.extend(criterios)
        return self

    def first(self):
        valores = [
            criterio.right.value
            for criterio in self.criterios
            if getattr(getattr(criterio, "right", None), "value", None) is not None
        ]
        id_rol, id_recurso, id_accion = valores[-3:]
        return object() if (id_rol, id_recurso, id_accion) in self.permisos else None


class DbPermisosFake:
    def __init__(self, permisos: set[tuple[int, int, int]]) -> None:
        self.permisos = permisos

    def query(self, *_args):
        return _QueryPermisoFake(self.permisos)


@contextmanager
def _client(
    monkeypatch: pytest.MonkeyPatch,
    usuario: UsuarioActual,
    permisos: set[tuple[int, int, int]],
    fincas: list[Finca],
) -> Generator[TestClient, None, None]:
    from src.configuration.infrastructure.routers import finca_router as modulo

    repo = FincaRepoFake(fincas)
    monkeypatch.setattr(modulo, "SqlAlchemyFincaRepository", lambda _db: repo)

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(modulo.router)
    app.dependency_overrides[get_current_user] = lambda: usuario
    app.dependency_overrides[get_db] = lambda: DbPermisosFake(permisos)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def _permiso(usuario: UsuarioActual, accion: int) -> tuple[int, int, int]:
    return usuario.id_rol, RECURSO_FINCAS, accion


def test_ingeniero_sin_finca_recibe_403_y_no_datos_de_finca_ajena(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    permisos = {_permiso(LECTOR_SIN_FINCA, ACCION_LEER)}

    with _client(monkeypatch, LECTOR_SIN_FINCA, permisos, [FINCA_AJENA]) as client:
        respuesta = client.get("/configuracion/fincas/19")

    assert respuesta.status_code == 403
    assert respuesta.json()["error_code"] == "FINCA_NO_AUTORIZADA"
    assert "id_finca" not in respuesta.json()
    assert "nombre" not in respuesta.json()


def test_ingeniero_sin_finca_recibe_listado_vacio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    permisos = {_permiso(LECTOR_SIN_FINCA, ACCION_LEER)}

    with _client(monkeypatch, LECTOR_SIN_FINCA, permisos, [FINCA_AJENA]) as client:
        respuesta = client.get("/configuracion/fincas")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"total": 0, "items": []}


def test_lector_asignado_solo_consulta_su_finca(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    permisos = {_permiso(LECTOR_ASIGNADO, ACCION_LEER)}

    with _client(
        monkeypatch,
        LECTOR_ASIGNADO,
        permisos,
        [FINCA_AJENA, FINCA_PROPIA],
    ) as client:
        listado = client.get("/configuracion/fincas")
        detalle = client.get("/configuracion/fincas/20")

    assert listado.status_code == 200
    assert [item["id_finca"] for item in listado.json()["items"]] == [20]
    assert detalle.status_code == 200
    assert detalle.json()["id_finca"] == 20


def test_permiso_de_gestion_conserva_alcance_global(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    permisos = {
        _permiso(GESTOR_GLOBAL, ACCION_LEER),
        _permiso(GESTOR_GLOBAL, ACCION_ACTUALIZAR),
    }

    with _client(
        monkeypatch,
        GESTOR_GLOBAL,
        permisos,
        [FINCA_AJENA, FINCA_PROPIA],
    ) as client:
        listado = client.get("/configuracion/fincas")
        detalle = client.get("/configuracion/fincas/19")

    assert listado.status_code == 200
    assert {item["id_finca"] for item in listado.json()["items"]} == {19, 20}
    assert detalle.status_code == 200
    assert detalle.json()["id_finca"] == 19


def test_finca_inexistente_conserva_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    permisos = {_permiso(LECTOR_SIN_FINCA, ACCION_LEER)}

    with _client(monkeypatch, LECTOR_SIN_FINCA, permisos, [FINCA_AJENA]) as client:
        respuesta = client.get("/configuracion/fincas/999")

    assert respuesta.status_code == 404
    assert respuesta.json()["error_code"] == "FINCA_NO_ENCONTRADA"


def test_rol_sin_lectura_sigue_bloqueado_por_rbac(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _client(monkeypatch, LECTOR_SIN_FINCA, set(), [FINCA_AJENA]) as client:
        respuesta = client.get("/configuracion/fincas/19")

    assert respuesta.status_code == 403
    assert respuesta.json()["error_code"] == "ACCESO_DENEGADO"

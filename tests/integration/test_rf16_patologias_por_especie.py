"""RF-16 / #1633 — Flujo de negocio de patologías por especie (endpoints reales).

Guardado: la base de pruebas actual solo tiene `modulo1`; estos tests **se saltan**
automáticamente si falta el schema `modulo9` o no hay especies activas. Quedan listos
para un entorno de CI con `modulo9` provisionado. La lógica pura (sin BD) se cubre en
`tests/configuration/test_rf16_*`.
"""
from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

_JWT_SECRET_INTEGRACION = "sgpmp-integration-tests-only"  # igual que conftest
_NOMBRE = "Zpatologia Integracion Test"


@pytest.fixture
def requiere_modulo9(db_session: Session) -> None:
    existe = db_session.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'modulo9'")
    ).first()
    if existe is None:
        pytest.skip("La base de pruebas no tiene el schema modulo9.")


@pytest.fixture
def dos_especies(db_session: Session, requiere_modulo9: None) -> list[int]:
    filas = db_session.execute(
        text("SELECT id_especie FROM modulo9.especies WHERE es_activo ORDER BY id_especie LIMIT 2")
    ).all()
    if len(filas) < 2:
        pytest.skip("Se requieren al menos 2 especies activas en modulo9.especies.")
    return [f[0] for f in filas]


@pytest.fixture
def config_client(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    from src.configuration.infrastructure.routers.patologia_router import router as patologia_router
    from src.identity_access.infrastructure.routers.usuarios_routers import router as usuarios_router  # noqa: F401
    from src.shared import jwt as jwt_module
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers

    monkeypatch.setattr(jwt_module, "_SECRET_KEY", _JWT_SECRET_INTEGRACION)
    monkeypatch.setattr(jwt_module, "_EXPIRE_HOURS", 8)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(patologia_router)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, client=("sgpmp-integration-tests", 50000), raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def _headers_vet(crear_usuario_db, crear_auth_headers) -> dict:
    vet = crear_usuario_db(id_rol=3, estado=2)  # Veterinario: C/R/U/D sobre recurso 18
    return crear_auth_headers(vet)


def test_mismo_nombre_en_dos_especies_y_dup_en_una(
    config_client, dos_especies, crear_usuario_db, crear_auth_headers
) -> None:
    e1, e2 = dos_especies
    h = _headers_vet(crear_usuario_db, crear_auth_headers)

    r1 = config_client.post("/configuracion/patologias", json={"id_especie": e1, "nombre": _NOMBRE}, headers=h)
    r2 = config_client.post("/configuracion/patologias", json={"id_especie": e2, "nombre": _NOMBRE}, headers=h)
    assert r1.status_code == 201, r1.text
    assert r2.status_code == 201, r2.text
    assert r1.json()["id_patologia"] is None  # entidad M09, no catálogo M04

    dup = config_client.post("/configuracion/patologias", json={"id_especie": e1, "nombre": _NOMBRE.lower()}, headers=h)
    assert dup.status_code == 409
    assert dup.json()["error_code"] == "PATOLOGIA_DUPLICADA_EN_ESPECIE"


def test_descripcion_independiente_por_especie(
    config_client, dos_especies, crear_usuario_db, crear_auth_headers
) -> None:
    e1, e2 = dos_especies
    h = _headers_vet(crear_usuario_db, crear_auth_headers)

    r1 = config_client.post(
        "/configuracion/patologias", json={"id_especie": e1, "nombre": _NOMBRE, "descripcion": "A"}, headers=h
    )
    config_client.post(
        "/configuracion/patologias", json={"id_especie": e2, "nombre": _NOMBRE, "descripcion": "B"}, headers=h
    )
    id1 = r1.json()["id_especies_patologias"]

    patch = config_client.patch(
        f"/configuracion/patologias/{id1}",
        json={"nombre": _NOMBRE, "descripcion": "A-editada", "fecha_actualizacion": None},
        headers=h,
    )
    assert patch.status_code == 200, patch.text

    lista_e2 = config_client.get(f"/configuracion/patologias?id_especie={e2}", headers=h).json()["items"]
    la_de_e2 = next(i for i in lista_e2 if i["nombre"] == _NOMBRE)
    assert la_de_e2["descripcion"] == "B"  # la especie 2 no cambió


def test_concurrencia_optimista_412(config_client, dos_especies, crear_usuario_db, crear_auth_headers) -> None:
    e1, _ = dos_especies
    h = _headers_vet(crear_usuario_db, crear_auth_headers)
    r1 = config_client.post("/configuracion/patologias", json={"id_especie": e1, "nombre": _NOMBRE}, headers=h)
    id1 = r1.json()["id_especies_patologias"]

    stale = datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat()
    patch = config_client.patch(
        f"/configuracion/patologias/{id1}",
        json={"nombre": _NOMBRE, "fecha_actualizacion": stale},
        headers=h,
    )
    assert patch.status_code == 412
    assert patch.json()["error_code"] == "CONFLICTO_CONCURRENCIA"


def test_desactivar_excluye_de_activas(config_client, dos_especies, crear_usuario_db, crear_auth_headers) -> None:
    e1, _ = dos_especies
    h = _headers_vet(crear_usuario_db, crear_auth_headers)
    r1 = config_client.post("/configuracion/patologias", json={"id_especie": e1, "nombre": _NOMBRE}, headers=h)
    id1 = r1.json()["id_especies_patologias"]

    off = config_client.patch(f"/configuracion/patologias/{id1}/desactivar", headers=h)
    assert off.status_code == 200, off.text
    assert off.json()["es_activo"] is False

    activas = config_client.get(f"/configuracion/patologias?id_especie={e1}&solo_activas=true", headers=h).json()["items"]
    assert all(i["id_especies_patologias"] != id1 for i in activas)

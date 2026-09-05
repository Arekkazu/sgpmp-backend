"""RF-17 — Catálogo de variables ambientales (`/configuracion/variables-ambientales`).

Prerequisito para que el frontend valide rango físico y contigüidad de
niveles de alerta con los IDs/nombres/unidades reales en vez de una copia
hardcodeada que podía desincronizarse del catálogo real.
"""
from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

_JWT_SECRET_INTEGRACION = "sgpmp-integration-tests-only"


@pytest.fixture
def config_client(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    from src.configuration.infrastructure.routers.variable_ambiental_router import router as variable_ambiental_router
    from src.shared import jwt as jwt_module
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers

    monkeypatch.setattr(jwt_module, "_SECRET_KEY", _JWT_SECRET_INTEGRACION)
    monkeypatch.setattr(jwt_module, "_EXPIRE_HOURS", 8)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(variable_ambiental_router)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, client=("sgpmp-integration-tests", 50000), raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def _hay_schema_modulo9(db_session: Session) -> bool:
    existe = db_session.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'modulo9'")
    ).first()
    return existe is not None


def test_veterinario_lista_catalogo_activo_200(config_client, db_session, crear_usuario_db, crear_auth_headers) -> None:
    if not _hay_schema_modulo9(db_session):
        pytest.skip("La base de pruebas no tiene el schema modulo9.")
    vet = crear_usuario_db(id_rol=3, estado=2)  # Veterinario: R sobre recurso 20
    headers = crear_auth_headers(vet)

    r = config_client.get("/configuracion/variables-ambientales", headers=headers)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == len(body["items"])
    assert body["total"] > 0
    primera = body["items"][0]
    assert {"id_variable_ambiental", "nombre", "unidad", "valor_fisico_min", "valor_fisico_max"} <= primera.keys()


def test_rol_sin_permiso_403(config_client, db_session, crear_usuario_db, crear_auth_headers) -> None:
    if not _hay_schema_modulo9(db_session):
        pytest.skip("La base de pruebas no tiene el schema modulo9.")
    productor = crear_usuario_db(id_rol=2, estado=2)  # Productor: sin permiso sobre recurso 20
    headers = crear_auth_headers(productor)

    r = config_client.get("/configuracion/variables-ambientales", headers=headers)

    assert r.status_code == 403
    assert r.json()["error_code"] == "ACCESO_DENEGADO"

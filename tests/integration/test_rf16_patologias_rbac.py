"""RF-16 / #1633 — Compuerta RBAC de patologías por especie (recurso 18).

Igual que `test_rbac_mod9_1634.py`: la base `pruebas` solo tiene el esquema `modulo1`,
no `modulo9`, así que se verifica la **compuerta** `require_permission` (401/403), no la
query de negocio. Un rol autorizado (Admin/Veterinario) pasa el RBAC y llega al use case
(puede fallar aguas abajo por falta de tablas modulo9 → 5xx, irrelevante al RBAC); un rol
sin permiso sobre el recurso 18 recibe 403 antes del use case.

La lógica de negocio por-especie se cubre en las pruebas unitarias
`tests/configuration/test_rf16_*`.
"""
from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

_JWT_SECRET_INTEGRACION = "sgpmp-integration-tests-only"  # igual que conftest


@pytest.fixture
def config_client(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
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
    with TestClient(
        app,
        client=("sgpmp-integration-tests", 50000),
        raise_server_exceptions=False,
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _body() -> dict:
    return {"id_especie": 1, "nombre": "Mastitis", "descripcion": "prueba"}


def test_productor_no_registra_patologia(config_client, crear_usuario_db, crear_auth_headers) -> None:
    """El Productor (rol 2) no tiene C sobre patologías (recurso 18) → 403."""
    productor = crear_usuario_db(id_rol=2, estado=2)
    respuesta = config_client.post(
        "/configuracion/patologias",
        json=_body(),
        headers=crear_auth_headers(productor),
    )
    assert respuesta.status_code == 403
    assert respuesta.json()["error_code"] == "ACCESO_DENEGADO"


def test_veterinario_pasa_rbac_patologia(config_client, crear_usuario_db, crear_auth_headers) -> None:
    """El Veterinario (rol 3) tiene C sobre patologías → el RBAC no bloquea (≠ 401/403)."""
    veterinario = crear_usuario_db(id_rol=3, estado=2)
    respuesta = config_client.post(
        "/configuracion/patologias",
        json=_body(),
        headers=crear_auth_headers(veterinario),
    )
    assert respuesta.status_code not in (401, 403)


def test_sin_token_no_autenticado(config_client) -> None:
    respuesta = config_client.post("/configuracion/patologias", json=_body())
    assert respuesta.status_code == 401

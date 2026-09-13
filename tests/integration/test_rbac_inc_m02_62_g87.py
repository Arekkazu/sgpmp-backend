"""Prueba de integración RBAC para INC-M02-62-G87 (RF-49/CU11).

El rol Productor tenía solo R (lectura) sobre el recurso `asociacion_sensor_activo`
(id_recurso=30) en `modulo1.permisos`, pese a que el RF-49 lo define como el actor
que decide qué sensores monitorean sus propios activos — POST devolvía 403
ACCESO_DENEGADO incluso sobre un activo de su propia finca. Se agregó el permiso
`prod_crear_asociacion_sensor_activo` (C sobre recurso 30) en `sgpmp` y `pruebas`.

Esta prueba verifica solo la **compuerta RBAC** (`require_permission`), no la lógica
de negocio del use case: usa un `id_activo` inexistente a propósito, así que lo
relevante es que la respuesta ya no sea 401/403 (la V1 de `AsociarSensorActivoUseCase`
responde 422 ACTIVO_NO_VALIDO aguas abajo, ver INC-M02-63-G88). El Veterinario, que
nunca tuvo C sobre este recurso, sirve de control negativo: debe seguir en 403.
"""
from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

_JWT_SECRET_INTEGRACION = "sgpmp-integration-tests-only"  # igual que conftest


@pytest.fixture
def m02_client(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    from src.biological_assets.infrastructure.routers.activo_biologico_router import router as activo_router
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
    app.include_router(activo_router)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(
        app,
        client=("sgpmp-integration-tests", 50000),
        raise_server_exceptions=False,
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _body_asociacion() -> dict:
    return {
        "tipo_activo": "INDIVIDUAL",
        "tipo_asociacion": "DIRECTA",
        "dispositivo_iot_id": 999999,
        "sensor_id": 999999,
        "id_infraestructura": 999999,
    }


def test_productor_ya_no_recibe_403_al_asociar_sensor(m02_client, crear_usuario_db, crear_auth_headers) -> None:
    """INC-M02-62-G87: el Productor ahora pasa el RBAC (≠ 401/403)."""
    productor = crear_usuario_db(id_rol=2, estado=2)

    respuesta = m02_client.post(
        "/activos-biologicos/999999/sensores",
        json=_body_asociacion(),
        headers=crear_auth_headers(productor),
    )

    assert respuesta.status_code not in (401, 403)


def test_veterinario_sigue_sin_permiso_para_asociar_sensor(m02_client, crear_usuario_db, crear_auth_headers) -> None:
    """Control negativo: el Veterinario nunca tuvo C sobre este recurso -> sigue en 403."""
    veterinario = crear_usuario_db(id_rol=3, estado=2)

    respuesta = m02_client.post(
        "/activos-biologicos/999999/sensores",
        json=_body_asociacion(),
        headers=crear_auth_headers(veterinario),
    )

    assert respuesta.status_code == 403
    assert respuesta.json()["error_code"] == "ACCESO_DENEGADO"

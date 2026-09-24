"""Prueba de integración RBAC para INC-M02-49-G84 (RF-49/CU11), issue #397.

El Administrador (y el Productor) recibían 403 ACCESO_DENEGADO al hacer PATCH
sobre una asociación sensor-activo (activar/desactivar, RF-49 Regla 5) porque
la migración 1d7d6069da52 (PR #286) sólo había insertado el permiso de CREAR
(id_accion=1) para Productor sobre el recurso 30 (`asociacion_sensor_activo`),
sin las tuplas de ACTUALIZAR (id_accion=3) que ese PATCH exige. La migración
c977eab2eb0d agrega `admin_actualizar_asociacion_sensor_activo` y
`prod_actualizar_asociacion_sensor_activo`.

Esta prueba verifica solo la **compuerta RBAC** (`require_permission`), no la
lógica de negocio del use case: usa un `id_asociacion` inexistente a
propósito, así que lo relevante es que la respuesta ya no sea 401/403
(`CambiarEstadoAsociacionSensorUseCase` responde 404 ASOCIACION_NO_ENCONTRADA
aguas abajo). El Veterinario, que solo tiene lectura (R) sobre este recurso,
sirve de control negativo: debe seguir en 403.
"""
from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

_JWT_SECRET_INTEGRACION = "sgpmp-integration-tests-only"  # igual que conftest


@pytest.fixture(autouse=True)
def permisos_actualizar_rf49(db_session: Session) -> None:
    """Representa el estado posterior a la migración c977eab2eb0d dentro del rollback del test."""
    db_session.execute(
        text(
            """
            INSERT INTO modulo1.permisos (
                nombre, descripcion, id_rol, id_recurso, id_accion, es_activo
            ) VALUES (
                'admin_actualizar_asociacion_sensor_activo',
                'Permite al Administrador activar/desactivar asociaciones sensor-activo de cualquier finca (RF-49 Regla 5).',
                1, 30, 3, TRUE
            )
            ON CONFLICT (id_rol, id_recurso, id_accion) DO NOTHING
            """
        )
    )
    db_session.execute(
        text(
            """
            INSERT INTO modulo1.permisos (
                nombre, descripcion, id_rol, id_recurso, id_accion, es_activo
            ) VALUES (
                'prod_actualizar_asociacion_sensor_activo',
                'Permite al Productor activar/desactivar asociaciones sensor-activo de sus propias fincas (RF-49 Regla 5).',
                2, 30, 3, TRUE
            )
            ON CONFLICT (id_rol, id_recurso, id_accion)
            DO UPDATE SET
                nombre = EXCLUDED.nombre,
                descripcion = EXCLUDED.descripcion,
                es_activo = TRUE
            """
        )
    )
    db_session.flush()


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


def test_admin_ya_no_recibe_403_al_desactivar_asociacion(m02_client, crear_usuario_db, crear_auth_headers) -> None:
    """INC-M02-49-G84 / #397: el Administrador ahora pasa el RBAC (≠ 401/403)."""
    admin = crear_usuario_db(id_rol=1, estado=2)

    respuesta = m02_client.patch(
        "/activos-biologicos/999999/sensores/999999",
        json={"estado_nuevo": "INACTIVA", "motivo": "mantenimiento"},
        headers=crear_auth_headers(admin),
    )

    assert respuesta.status_code == 404
    assert respuesta.json()["error_code"] == "ASOCIACION_NO_ENCONTRADA"


def test_productor_ya_no_recibe_403_al_desactivar_asociacion(m02_client, crear_usuario_db, crear_auth_headers) -> None:
    productor = crear_usuario_db(id_rol=2, estado=2)

    respuesta = m02_client.patch(
        "/activos-biologicos/999999/sensores/999999",
        json={"estado_nuevo": "INACTIVA", "motivo": "mantenimiento"},
        headers=crear_auth_headers(productor),
    )

    assert respuesta.status_code == 404
    assert respuesta.json()["error_code"] == "ASOCIACION_NO_ENCONTRADA"


def test_veterinario_sigue_sin_permiso_para_actualizar_asociacion(m02_client, crear_usuario_db, crear_auth_headers) -> None:
    """Control negativo: el Veterinario solo tiene lectura (R) sobre este recurso -> sigue en 403."""
    veterinario = crear_usuario_db(id_rol=3, estado=2)

    respuesta = m02_client.patch(
        "/activos-biologicos/999999/sensores/999999",
        json={"estado_nuevo": "INACTIVA", "motivo": "mantenimiento"},
        headers=crear_auth_headers(veterinario),
    )

    assert respuesta.status_code == 403
    assert respuesta.json()["error_code"] == "ACCESO_DENEGADO"

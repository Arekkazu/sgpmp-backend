"""Prueba de integración RBAC para INC-M02-62-G87 (RF-49/CU11).

El rol Productor tenía solo R (lectura) sobre el recurso `asociacion_sensor_activo`
(id_recurso=30) en `modulo1.permisos`, pese a que el RF-49 lo define como el actor
que decide qué sensores monitorean sus propios activos — POST devolvía 403
ACCESO_DENEGADO incluso sobre un activo de su propia finca. La migración
v5.3.0 agrega `prod_crear_asociacion_sensor_activo` (C sobre recurso 30).

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
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

_JWT_SECRET_INTEGRACION = "sgpmp-integration-tests-only"  # igual que conftest


@pytest.fixture(autouse=True)
def permiso_productor_rf49(db_session: Session) -> None:
    """Representa el estado posterior a la migración dentro del rollback del test."""
    db_session.execute(
        text(
            """
            INSERT INTO modulo1.permisos (
                nombre, descripcion, id_rol, id_recurso, id_accion, es_activo
            ) VALUES (
                'prod_crear_asociacion_sensor_activo',
                'Permite al Productor asociar sensores IoT a activos e infraestructuras de sus propias fincas (RF-49).',
                2, 30, 1, TRUE
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

    assert respuesta.status_code == 422
    assert respuesta.json()["error_code"] == "ACTIVO_NO_ENCONTRADO"


def test_productor_llega_al_flujo_funcional_sobre_activo_de_su_finca(
    m02_client,
    db_session: Session,
    crear_auth_headers,
) -> None:
    contexto = db_session.execute(
        text(
            """
            SELECT
                u.id_usuario,
                c.id_cuenta_usuario,
                u.id_rol,
                u.version,
                u.correo_electronico AS correo,
                a.id_activo_biologico
            FROM modulo1.usuarios u
            JOIN modulo1.cuentas_usuarios c ON c.id_usuario = u.id_usuario
            JOIN modulo9.fincas f ON f.id_usuario = u.id_usuario
            JOIN modulo9.infraestructuras i ON i.id_finca = f.id_finca
            JOIN modulo2.activos_biologicos a
              ON a.id_infraestructura = i.id_infraestructura
            WHERE u.id_rol = 2 AND c.id_estado_cuenta = 2
            ORDER BY u.id_usuario, a.id_activo_biologico
            LIMIT 1
            """
        )
    ).mappings().one_or_none()
    if contexto is None:
        pytest.skip("La base no contiene un Productor activo con un activo en su finca.")

    id_activo = contexto["id_activo_biologico"]
    usuario = {clave: valor for clave, valor in contexto.items() if clave != "id_activo_biologico"}
    # La cuenta oficial puede tener una sesión activa. Se desactiva solo dentro
    # de la transacción exterior para poder emitir el JWT de prueba; el rollback
    # restaura el estado original al terminar.
    db_session.execute(
        text(
            """
            UPDATE modulo1.sesiones
            SET es_activa = FALSE
            WHERE id_cuenta_usuario = :id_cuenta AND es_activa = TRUE
            """
        ),
        {"id_cuenta": usuario["id_cuenta_usuario"]},
    )
    db_session.execute(
        text(
            """
            UPDATE modulo1.cuentas_usuarios
            SET ultimo_acceso = now()
            WHERE id_cuenta_usuario = :id_cuenta
            """
        ),
        {"id_cuenta": usuario["id_cuenta_usuario"]},
    )
    db_session.flush()
    respuesta = m02_client.post(
        f"/activos-biologicos/{id_activo}/sensores",
        json=_body_asociacion(),
        headers=crear_auth_headers(usuario),
    )

    # Pasó RBAC y alcance; el sensor deliberadamente inexistente detiene V3.
    assert respuesta.status_code == 404
    assert respuesta.json()["error_code"] == "SENSOR_NO_ENCONTRADO"


def test_productor_no_puede_asociar_sensor_a_activo_de_finca_ajena(
    m02_client,
    db_session: Session,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    """El nuevo CREATE no habilita BOLA sobre activos de otras fincas."""
    id_activo_ajeno = db_session.execute(
        text(
            """
            SELECT a.id_activo_biologico
            FROM modulo2.activos_biologicos a
            JOIN modulo9.infraestructuras i
              ON i.id_infraestructura = a.id_infraestructura
            WHERE i.id_finca IS NOT NULL
            ORDER BY a.id_activo_biologico
            LIMIT 1
            """
        )
    ).scalar_one_or_none()
    if id_activo_ajeno is None:
        pytest.skip("La base no contiene un activo asociado a una finca.")

    # Usuario nuevo sin fincas: cualquier activo existente queda fuera de su alcance.
    productor = crear_usuario_db(id_rol=2, estado=2)
    respuesta = m02_client.post(
        f"/activos-biologicos/{id_activo_ajeno}/sensores",
        json=_body_asociacion(),
        headers=crear_auth_headers(productor),
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["error_code"] == "ACTIVO_NO_ENCONTRADO"


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

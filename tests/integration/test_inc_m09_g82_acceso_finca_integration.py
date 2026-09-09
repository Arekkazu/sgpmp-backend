"""Integración INC-M09-G82 sobre RBAC, autenticación y repositorio PostgreSQL."""
from __future__ import annotations

import json
import uuid
from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

_JWT_SECRET_INTEGRACION = "sgpmp-integration-tests-only"


@pytest.fixture
def config_client(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    from src.configuration.infrastructure.routers.finca_router import router as finca_router
    from src.identity_access.infrastructure.routers.usuarios_routers import (
        router as usuarios_router,  # noqa: F401
    )
    from src.shared import jwt as jwt_module
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers

    monkeypatch.setattr(jwt_module, "_SECRET_KEY", _JWT_SECRET_INTEGRACION)
    monkeypatch.setattr(jwt_module, "_EXPIRE_HOURS", 8)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(finca_router)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
    app.dependency_overrides.clear()


def _id_rol(db_session: Session, nombre: str) -> int:
    return db_session.execute(
        text("SELECT id_rol FROM modulo1.roles WHERE nombre_rol = :nombre"),
        {"nombre": nombre},
    ).scalar_one()


def _nombre_finca() -> str:
    traduccion = str.maketrans("0123456789abcdef", "abcdefghijklmnop")
    return "Finca Integracion " + uuid.uuid4().hex[:12].translate(traduccion)


def _crear_finca(db_session: Session, id_usuario: int) -> int:
    ubicacion = json.dumps(
        {
            "departamento": "Huila",
            "municipio": "Neiva",
            "vereda": "Centro",
            "latitud": "2.93",
            "longitud": "-75.28",
        }
    )
    id_finca = db_session.execute(
        text(
            """
            INSERT INTO modulo9.fincas (
                nombre, ubicacion, tamano_h, fecha_actualizacion,
                fecha_creacion, es_activo, id_usuario
            ) VALUES (
                :nombre, CAST(:ubicacion AS jsonb), 10.00, now(), now(), true, :id_usuario
            )
            RETURNING id_finca
            """
        ),
        {
            "nombre": _nombre_finca(),
            "ubicacion": ubicacion,
            "id_usuario": id_usuario,
        },
    ).scalar_one()
    db_session.flush()
    return id_finca


def test_ingeniero_sin_finca_no_obtiene_datos_ajenos(
    config_client: TestClient,
    db_session: Session,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    ingeniero = crear_usuario_db(id_rol=_id_rol(db_session, "Ingeniero de Campo"), estado=2)
    propietario = crear_usuario_db(id_rol=_id_rol(db_session, "Productor"), estado=2)
    id_finca_ajena = _crear_finca(db_session, propietario["id_usuario"])
    headers = crear_auth_headers(ingeniero)

    detalle = config_client.get(f"/configuracion/fincas/{id_finca_ajena}", headers=headers)
    listado = config_client.get("/configuracion/fincas", headers=headers)

    assert detalle.status_code == 403
    assert detalle.json()["error_code"] == "FINCA_NO_AUTORIZADA"
    assert "id_finca" not in detalle.json()
    assert "nombre" not in detalle.json()
    assert listado.status_code == 200
    assert listado.json() == {"total": 0, "items": []}


def test_ingeniero_asignado_consulta_solo_su_finca(
    config_client: TestClient,
    db_session: Session,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    ingeniero = crear_usuario_db(id_rol=_id_rol(db_session, "Ingeniero de Campo"), estado=2)
    propietario = crear_usuario_db(id_rol=_id_rol(db_session, "Productor"), estado=2)
    id_finca_propia = _crear_finca(db_session, ingeniero["id_usuario"])
    id_finca_ajena = _crear_finca(db_session, propietario["id_usuario"])
    headers = crear_auth_headers(ingeniero)

    detalle = config_client.get(f"/configuracion/fincas/{id_finca_propia}", headers=headers)
    listado = config_client.get("/configuracion/fincas", headers=headers)

    assert detalle.status_code == 200
    assert detalle.json()["id_finca"] == id_finca_propia
    assert listado.status_code == 200
    assert [item["id_finca"] for item in listado.json()["items"]] == [id_finca_propia]
    assert id_finca_ajena not in {item["id_finca"] for item in listado.json()["items"]}


def test_administrador_conserva_consulta_global(
    config_client: TestClient,
    db_session: Session,
    crear_usuario_db,
    crear_auth_headers,
) -> None:
    administrador = crear_usuario_db(id_rol=_id_rol(db_session, "Administrador"), estado=2)
    propietario = crear_usuario_db(id_rol=_id_rol(db_session, "Productor"), estado=2)
    id_finca_ajena = _crear_finca(db_session, propietario["id_usuario"])
    headers = crear_auth_headers(administrador)

    detalle = config_client.get(f"/configuracion/fincas/{id_finca_ajena}", headers=headers)
    listado = config_client.get("/configuracion/fincas", headers=headers)

    assert detalle.status_code == 200
    assert detalle.json()["id_finca"] == id_finca_ajena
    assert id_finca_ajena in {item["id_finca"] for item in listado.json()["items"]}

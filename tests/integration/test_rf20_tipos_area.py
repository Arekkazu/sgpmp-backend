"""RF-20 — Catálogo administrable de tipos de área (`/configuracion/tipos-area`).

`tipo_area` era un enum fijo de Postgres (`enum_tipo_infraestructura`, 5 valores
en minúscula sin tilde) que el DTO de `RegistrarInfraestructuraDTO` nunca podía
satisfacer con los valores capitalizados/con tilde que el frontend enviaba
('Galpón' vs 'galpon'). Este catálogo reemplaza el enum: el Administrador
puede registrar/desactivar tipos, y `registrar_infraestructura` valida contra
él en vez de contra un tipo fijo.

Requiere que, además de `TEST_DATABASE_URL`, la base de pruebas tenga
aplicadas las filas de RBAC del recurso 58 (`tipos_area`) documentadas en la
migración `2dbb6d44046f` — la RBAC de este proyecto no se versiona por
Alembic, así que estas pruebas se saltan (403 inesperado) si esas filas no
existen todavía en el entorno donde corren.
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
    from src.configuration.infrastructure.routers.tipo_area_router import router as tipo_area_router
    from src.configuration.infrastructure.routers.infraestructura_router import router as infraestructura_router
    from src.shared import jwt as jwt_module
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers

    monkeypatch.setattr(jwt_module, "_SECRET_KEY", _JWT_SECRET_INTEGRACION)
    monkeypatch.setattr(jwt_module, "_EXPIRE_HOURS", 8)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(tipo_area_router)
    app.include_router(infraestructura_router)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, client=("sgpmp-integration-tests", 50000), raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def _hay_catalogo_tipos_area(db_session: Session) -> bool:
    existe = db_session.execute(
        text("SELECT 1 FROM information_schema.tables WHERE table_schema = 'modulo9' AND table_name = 'tipos_area'")
    ).first()
    return existe is not None


def test_admin_registra_tipo_de_area_201(config_client, db_session, crear_usuario_db, crear_auth_headers) -> None:
    if not _hay_catalogo_tipos_area(db_session):
        pytest.skip("La base de pruebas no tiene aplicada la migracion 2dbb6d44046f.")
    admin = crear_usuario_db(id_rol=1, estado=2)
    headers = crear_auth_headers(admin)

    r = config_client.post("/configuracion/tipos-area", json={"nombre": "Jaula"}, headers=headers)

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["nombre"] == "Jaula"
    assert body["es_activo"] is True


def test_nombre_duplicado_409(config_client, db_session, crear_usuario_db, crear_auth_headers) -> None:
    if not _hay_catalogo_tipos_area(db_session):
        pytest.skip("La base de pruebas no tiene aplicada la migracion 2dbb6d44046f.")
    admin = crear_usuario_db(id_rol=1, estado=2)
    headers = crear_auth_headers(admin)
    config_client.post("/configuracion/tipos-area", json={"nombre": "Corral Techado"}, headers=headers)

    r = config_client.post("/configuracion/tipos-area", json={"nombre": "Corral Techado"}, headers=headers)

    assert r.status_code == 409
    assert r.json()["error_code"] == "TIPO_AREA_DUPLICADO"


def test_listar_solo_activos_excluye_desactivados(config_client, db_session, crear_usuario_db, crear_auth_headers) -> None:
    if not _hay_catalogo_tipos_area(db_session):
        pytest.skip("La base de pruebas no tiene aplicada la migracion 2dbb6d44046f.")
    admin = crear_usuario_db(id_rol=1, estado=2)
    headers = crear_auth_headers(admin)
    nuevo = config_client.post("/configuracion/tipos-area", json={"nombre": "Acuario"}, headers=headers).json()

    config_client.patch(f"/configuracion/tipos-area/{nuevo['id_tipo_area']}/desactivar", headers=headers)
    r = config_client.get("/configuracion/tipos-area", params={"solo_activos": True}, headers=headers)

    assert r.status_code == 200, r.text
    nombres = [item["nombre"] for item in r.json()["items"]]
    assert "Acuario" not in nombres


def test_desactivar_dos_veces_422(config_client, db_session, crear_usuario_db, crear_auth_headers) -> None:
    if not _hay_catalogo_tipos_area(db_session):
        pytest.skip("La base de pruebas no tiene aplicada la migracion 2dbb6d44046f.")
    admin = crear_usuario_db(id_rol=1, estado=2)
    headers = crear_auth_headers(admin)
    nuevo = config_client.post("/configuracion/tipos-area", json={"nombre": "Vivero"}, headers=headers).json()
    config_client.patch(f"/configuracion/tipos-area/{nuevo['id_tipo_area']}/desactivar", headers=headers)

    r = config_client.patch(f"/configuracion/tipos-area/{nuevo['id_tipo_area']}/desactivar", headers=headers)

    assert r.status_code == 422
    assert r.json()["error_code"] == "TIPO_AREA_YA_INACTIVO"


def test_registrar_infraestructura_con_tipo_inexistente_422(
    config_client, db_session, crear_usuario_db, crear_auth_headers
) -> None:
    if not _hay_catalogo_tipos_area(db_session):
        pytest.skip("La base de pruebas no tiene aplicada la migracion 2dbb6d44046f.")
    admin = crear_usuario_db(id_rol=1, estado=2)
    headers = crear_auth_headers(admin)
    id_finca = db_session.execute(
        text(
            """
            INSERT INTO modulo9.fincas (nombre, ubicacion, tamano_h, fecha_actualizacion, fecha_creacion, es_activo)
            VALUES (:nombre, CAST(:ubicacion AS jsonb), 10.00, now(), now(), true)
            RETURNING id_finca
            """
        ),
        {"nombre": f"Finca RF-20 {id(headers)}", "ubicacion": '{"departamento": "Huila", "municipio": "Neiva"}'},
    ).scalar_one()
    db_session.flush()

    r = config_client.post(
        "/configuracion/infraestructuras",
        json={
            "nombre_infraestructura": "Area de prueba RF-20",
            "tipo_area": "Tipo Que No Existe",
            "superficie": "10.00",
            "finca_id": id_finca,
        },
        headers=headers,
    )

    assert r.status_code == 422, r.text
    assert r.json()["error_code"] == "TIPO_AREA_NO_RECONOCIDO"

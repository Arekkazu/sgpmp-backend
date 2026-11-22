# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-19 RF-15: esperanza_vida_dias por la API contra la columna de DB-07 (RFC-014) |
"""DEV-19 (RFC-014): registrar y editar una especie con esperanza de vida.

Requiere la BD con DB-07 aplicada (``especies.esperanza_vida_dias``).
"""
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

pytestmark = pytest.mark.integration


@pytest.fixture
def cliente(db_session, integration_app, monkeypatch):
    from src.configuration.infrastructure.routers.especie_router import router as especies
    from src.shared import jwt as jwt_module
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers

    monkeypatch.setattr(jwt_module, "_SECRET_KEY", "sgpmp-integration-tests-only")
    monkeypatch.setattr(jwt_module, "_EXPIRE_HOURS", 8)
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(especies)
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_registrar_editar_y_rechazar_esperanza_de_vida(cliente, db_session, crear_usuario_db, crear_auth_headers):
    headers = crear_auth_headers(crear_usuario_db(id_rol=1, estado=2))
    nombre = "Cachama " + uuid4().hex[:8].translate(str.maketrans("0123456789abcdef", "abcdefghijklmnop"))

    r = cliente.post("/configuracion/especies", headers=headers,
                     json={"nombre": nombre, "grupo_manejo": "ACUICULTURA", "esperanza_vida_dias": 730})
    assert r.status_code == 201, r.text
    especie = r.json()
    assert especie["esperanza_vida_dias"] == 730

    r = cliente.patch(f"/configuracion/especies/{especie['id_especie']}", headers=headers, json={
        "nombre": nombre, "esperanza_vida_dias": 400, "fecha_actualizacion": especie["fecha_actualizacion"]})
    assert r.status_code == 200, r.text
    assert r.json()["esperanza_vida_dias"] == 400
    assert db_session.execute(text("SELECT esperanza_vida_dias FROM modulo9.especies WHERE id_especie = :i"),
                              {"i": especie["id_especie"]}).scalar_one() == 400

    r = cliente.post("/configuracion/especies", headers=headers,
                     json={"nombre": nombre + " b", "grupo_manejo": "ACUICULTURA", "esperanza_vida_dias": 0})
    assert r.status_code == 400, r.text

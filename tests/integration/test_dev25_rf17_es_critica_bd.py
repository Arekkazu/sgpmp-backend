# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-25 RF-17: PATCH es_critica con el permiso de DB-08 (Administrador 200, Veterinario 403) |
# | 2026-10-23 | Arekkazu | DEV-25 RF-17: docstring con el recurso variables_ambientales_criticas |
"""DEV-25 (RFC-016 B.7): solo el Administrador marca una variable como crítica y el
cambio queda en ``modulo1.eventos``.

Requiere la BD con DB-08 aplicada: el Veterinario conserva U sobre
``umbrales_ambientales`` pero no tiene ``variables_ambientales_criticas``. El tipo de
evento 31 lo siembra 4792129a64e6; la prueba lo inserta si falta.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

pytestmark = pytest.mark.integration


@pytest.fixture
def cliente(db_session, integration_app, monkeypatch):
    from src.configuration.infrastructure.routers.variable_ambiental_router import router as variables
    from src.shared import jwt as jwt_module
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers

    monkeypatch.setattr(jwt_module, "_SECRET_KEY", "sgpmp-integration-tests-only")
    monkeypatch.setattr(jwt_module, "_EXPIRE_HOURS", 8)
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(variables)
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_solo_el_administrador_marca_la_variable_como_critica(
    cliente, db_session, crear_usuario_db, crear_auth_headers
):
    db_session.execute(text("""
        INSERT INTO modulo1.tipos_eventos (id_tipo_evento, nombre, accion)
        VALUES (31, 'CAMBIO_VARIABLE_CRITICA', 'Cambio de criticidad de una variable ambiental')
        ON CONFLICT (id_tipo_evento) DO NOTHING
    """))
    variable = db_session.execute(text(
        "SELECT id_variable_ambiental FROM modulo9.variables_ambientales WHERE es_activo AND NOT es_critica LIMIT 1"
    )).scalar_one()
    admin = crear_usuario_db(id_rol=1, estado=2)
    veterinario = crear_usuario_db(id_rol=3, estado=2)
    headers_admin = crear_auth_headers(admin)

    r = cliente.patch(f"/configuracion/variables-ambientales/{variable}", json={"es_critica": True},
                      headers=crear_auth_headers(veterinario))
    assert r.status_code == 403, r.text

    r = cliente.patch(f"/configuracion/variables-ambientales/{variable}", json={"es_critica": True},
                      headers=headers_admin)
    assert r.status_code == 200, r.text
    assert r.json()["es_critica"] is True

    r = cliente.get("/configuracion/variables-ambientales", headers=headers_admin)
    assert {v["id_variable_ambiental"]: v["es_critica"] for v in r.json()["items"]}[variable] is True
    evento = db_session.execute(text(
        "SELECT id_usuario, detalle FROM modulo1.eventos WHERE tipo_evento = 31 ORDER BY id_evento DESC LIMIT 1"
    )).one()
    assert evento.id_usuario == admin["id_usuario"]
    assert evento.detalle["valores_nuevos"]["es_critica"] is True

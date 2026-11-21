# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-171-G78 RF-57: filtros fuera del catálogo responden 400 VAL_ENTRADA |
"""INC-M03-171-G78 (RF-57 FA-09, TC-M03-G78): GET /iot/alertas con un filtro fuera del catálogo.

Antes: 500 ERROR_INTERNO (el valor llegaba al CAST a enum de PostgreSQL). Ahora: 400 VAL_ENTRADA.
"""
import importlib
import pkgutil

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.telemetry.infrastructure.routers import alerta_router, infraestructura_iot_router

pytestmark = pytest.mark.integration

VALIDOS = {"estado": "ACTIVA", "severidad": "CRITICO", "tipo_alerta": "ESTRES_TERMICO", "origen_evento": "EDGE"}


@pytest.fixture(autouse=True)
def modelos():
    for paquete in ("src.configuration.infrastructure.models", "src.biological_assets.infrastructure.models",
                    "src.telemetry.infrastructure.models", "src.identity_access.infrastructure.models"):
        modulo = importlib.import_module(paquete)
        for item in pkgutil.iter_modules(modulo.__path__, paquete + "."):
            importlib.import_module(item.name)


@pytest.fixture
def http(db_session, crear_usuario_db, crear_auth_headers, monkeypatch):
    from src.shared import jwt as jwt_module
    monkeypatch.setattr(jwt_module, "_SECRET_KEY", "sgpmp-integration-tests-only")
    rol = db_session.execute(text("SELECT id_rol FROM modulo1.roles WHERE nombre_rol='Administrador'")).scalar_one()
    admin = crear_auth_headers(crear_usuario_db(id_rol=rol))
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(alerta_router.router)
    app.include_router(infraestructura_iot_router.router)

    def sesion():
        db_session.info.clear()
        return db_session

    app.dependency_overrides[get_db] = sesion
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, admin


@pytest.mark.parametrize("filtro", list(VALIDOS))
@pytest.mark.parametrize("valor", ["INEXISTENTE", "activa"])
def test_filtro_fuera_del_catalogo_es_400(http, filtro, valor):
    client, admin = http
    r = client.get("/iot/alertas", headers=admin, params={filtro: valor})
    assert r.status_code == 400, r.text
    cuerpo = r.json()
    assert cuerpo["error_code"] == "VAL_ENTRADA"
    assert filtro in r.text


@pytest.mark.parametrize("filtro,valor", list(VALIDOS.items()) + [("tipo_alerta", "TECNICA"),
                                                                ("origen_evento", "HEARTBEAT")])
def test_valor_del_catalogo_responde_200(http, filtro, valor):
    client, admin = http
    r = client.get("/iot/alertas", headers=admin, params={filtro: valor})
    assert r.status_code == 200, r.text
    assert "total" in r.json()


@pytest.mark.parametrize("filtro", list(VALIDOS))
def test_filtro_vacio_sigue_siendo_sin_filtro(http, filtro):
    """``?estado=`` respondía 200 sin filtrar; se conserva para no romper clientes."""
    client, admin = http
    assert client.get("/iot/alertas", headers=admin, params={filtro: ""}).status_code == 200


def test_todos_los_filtros_validos_a_la_vez(http):
    client, admin = http
    assert client.get("/iot/alertas", headers=admin, params=VALIDOS).status_code == 200


@pytest.mark.parametrize("filtro", ["estado", "severidad"])
def test_alertas_tecnicas_tambien_valida_sus_filtros(http, filtro):
    client, admin = http
    assert client.get("/iot/alertas-tecnicas", headers=admin, params={filtro: "INEXISTENTE"}).status_code == 400
    assert client.get("/iot/alertas-tecnicas", headers=admin, params={filtro: VALIDOS[filtro]}).status_code == 200

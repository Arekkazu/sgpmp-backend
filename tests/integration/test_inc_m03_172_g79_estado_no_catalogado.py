# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-172-G79 RF-57 CA-11: estado no catalogado → 422 TRANSICION_INVALIDA |
"""INC-M03-172-G79 (RF-57 CA-11, aclaración RFC-008): PATCH /iot/alertas/{id}/estado.

Un estado fuera del catálogo (FINALIZADA, vacío, null, CERRADA) es una transición inválida: 422
TRANSICION_INVALIDA, la alerta no cambia y el rechazo queda en la bitácora. Antes: 400 VAL_ENTRADA.
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


def _alerta(db, tipo="ESTRES_TERMICO"):
    id_alerta = db.execute(text("""INSERT INTO modulo3.alertas(tipo_alerta,severidad,estado_alerta,origen_evento,
        tipo_variable,fecha_evento,fecha_generacion) VALUES (:t,'LEVE','ACTIVA','EDGE','TEMPERATURA_AMBIENTAL',now(),now())
        RETURNING id_alerta"""), {"t": tipo}).scalar_one()
    db.commit()
    return id_alerta


def _estado(db, id_alerta):
    return db.execute(text("SELECT estado_alerta::text FROM modulo3.alertas WHERE id_alerta=:id"),
                      {"id": id_alerta}).scalar_one()


@pytest.mark.parametrize("valor", ["FINALIZADA", "", None, "CERRADA", "cerrada", "   "])
def test_estado_no_catalogado_es_422_transicion_invalida(http, db_session, valor):
    client, admin = http
    id_alerta = _alerta(db_session)
    r = client.patch(f"/iot/alertas/{id_alerta}/estado", headers=admin, json={"nuevo_estado": valor})
    assert r.status_code == 422, r.text
    assert r.json()["error_code"] == "TRANSICION_INVALIDA"
    assert _estado(db_session, id_alerta) == "ACTIVA"
    assert db_session.execute(text(
        "SELECT count(*) FROM modulo3.bitacora_auditoria_iot WHERE tipo_evento='TRANSICION_ALERTA_RECHAZADA' "
        "AND entidad_afectada_id=:id"), {"id": str(id_alerta)}).scalar_one() == 1


@pytest.mark.parametrize("cuerpo", [{}, {"nuevo_estado": 5}, {"nuevo_estado": ["EN_ATENCION"]}])
def test_cuerpo_mal_formado_sigue_siendo_400(http, db_session, cuerpo):
    client, admin = http
    id_alerta = _alerta(db_session)
    r = client.patch(f"/iot/alertas/{id_alerta}/estado", headers=admin, json=cuerpo)
    assert r.status_code == 400 and r.json()["error_code"] == "VAL_ENTRADA", r.text


def test_transicion_valida_sigue_funcionando(http, db_session):
    client, admin = http
    id_alerta = _alerta(db_session)
    r = client.patch(f"/iot/alertas/{id_alerta}/estado", headers=admin, json={"nuevo_estado": "en_atencion"})
    assert r.status_code == 200, r.text
    assert _estado(db_session, id_alerta) == "EN_ATENCION"


def test_alertas_tecnicas_aplica_la_misma_regla(http, db_session):
    client, admin = http
    id_alerta = _alerta(db_session, tipo="TECNICA")
    r = client.patch(f"/iot/alertas-tecnicas/{id_alerta}/estado", headers=admin, json={"nuevo_estado": "FINALIZADA"})
    assert r.status_code == 422 and r.json()["error_code"] == "TRANSICION_INVALIDA", r.text

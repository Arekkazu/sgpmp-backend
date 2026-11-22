# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-165-G71 RF-63: la bitácora se consulta con los nombres de RF-57 y del catálogo |
"""INC-M03-165-G71 (RF-63, TC-M03-G71/G74/G79): tipos de evento del ciclo de la alerta en la bitácora.

Por HTTP: se generan los eventos con POST/PATCH reales y se consultan con GET /iot/auditoria,
igual que QA, por el nombre del texto de RF-57 y por el del catálogo de RF-63.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from src.shared.database import get_db, get_db_sistema
from src.shared.error_handlers import register_error_handlers
from src.telemetry.infrastructure.routers import alerta_router, auditoria_iot_router
from tests.integration.test_inc_m03_164_g71_e14_reglas_multiples import (  # noqa: F401
    _evento, _lectura, area, modelos,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def http(db_session, crear_usuario_db, crear_auth_headers, monkeypatch, headers_broker):
    from src.shared import jwt as jwt_module
    monkeypatch.setattr(jwt_module, "_SECRET_KEY", "sgpmp-integration-tests-only")
    rol_admin = db_session.execute(text("SELECT id_rol FROM modulo1.roles WHERE nombre_rol='Administrador'")).scalar_one()
    admin = crear_auth_headers(crear_usuario_db(id_rol=rol_admin))
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(alerta_router.router)
    app.include_router(auditoria_iot_router.router)

    def sesion():
        db_session.info.clear()
        return db_session

    app.dependency_overrides[get_db] = sesion
    app.dependency_overrides[get_db_sistema] = sesion
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, admin, headers_broker, db_session


def _bitacora(http, tipo_evento, id_alerta):
    client, admin, _, _ = http
    r = client.get("/iot/auditoria", headers=admin,
                   params={"tipo_evento": tipo_evento, "entidad_afectada_id": str(id_alerta)})
    assert r.status_code == 200, r.text
    return r.json()


def _alerta_con_humedad(db_session, http, area):
    hw = area()
    _lectura(db_session, hw, "HUMEDAD_RELATIVA", "75")
    r = _evento(http, hw, "TEMPERATURA_AMBIENTAL", "31.0")
    assert r.status_code == 201, r.text
    return hw, r.json()["id_alerta"]


def test_g74_evento_consolidado_por_e4_se_encuentra_como_evento_correlacionado(db_session, http, area):
    hw, id_alerta = _alerta_con_humedad(db_session, http, area)
    assert _bitacora(http, "EVENTO_CORRELACIONADO", id_alerta)["total"] == 0
    segundo = _evento(http, hw, "TEMPERATURA_AMBIENTAL", "37.0", severidad="CRITICO")  # mismo sensor y variable
    assert segundo.json()["es_duplicado"] and segundo.json()["alerta_existente_id"] == id_alerta, segundo.text
    por_rf57 = _bitacora(http, "EVENTO_CORRELACIONADO", id_alerta)
    por_catalogo = _bitacora(http, "DUPLICADO_ALERTA_CORRELACIONADO", id_alerta)
    assert por_rf57["total"] == por_catalogo["total"] == 1
    assert por_rf57["items"][0]["tipo_evento"] == "DUPLICADO_ALERTA_CORRELACIONADO"


def test_g79_cambios_de_estado_se_encuentran_como_estado_cambiado(db_session, http, area):
    _, id_alerta = _alerta_con_humedad(db_session, http, area)
    client, admin, _, _ = http
    for estado in ("EN_ATENCION", "RESUELTA"):
        r = client.patch(f"/iot/alertas/{id_alerta}/estado", headers=admin,
                         json={"nuevo_estado": estado, "motivo": "Prueba G79"})
        assert r.status_code == 200, r.text
    cambios = _bitacora(http, "ESTADO_CAMBIADO", id_alerta)
    assert cambios["total"] == 2
    assert {i["tipo_evento"] for i in cambios["items"]} == {"ALERTA_RECONOCIDA", "ALERTA_RESUELTA"}
    assert _bitacora(http, "ALERTA_RESUELTA", id_alerta)["total"] == 1  # el nombre del catálogo sigue igual


def test_g79_descarte_tambien_es_estado_cambiado(db_session, http, area):
    _, id_alerta = _alerta_con_humedad(db_session, http, area)
    client, admin, _, _ = http
    r = client.patch(f"/iot/alertas/{id_alerta}/estado", headers=admin,
                     json={"nuevo_estado": "DESCARTADA", "motivo": "Falso positivo de prueba"})
    assert r.status_code == 200, r.text
    assert [i["tipo_evento"] for i in _bitacora(http, "ESTADO_CAMBIADO", id_alerta)["items"]] == ["ALERTA_DESCARTADA"]


def test_g71_correlacion_y_consolidacion_dejan_reglas_multiples_correlacionadas(db_session, http, area):
    hw, id_alerta = _alerta_con_humedad(db_session, http, area)
    assert _bitacora(http, "REGLAS_MULTIPLES_CORRELACIONADAS", id_alerta)["total"] == 1  # creación (E14)
    otro = _evento(http, hw, "HUMEDAD_RELATIVA", "75")  # el otro sensor se consolida (E15)
    assert otro.json()["alerta_existente_id"] == id_alerta, otro.text
    entradas = _bitacora(http, "REGLAS_MULTIPLES_CORRELACIONADAS", id_alerta)["items"]
    assert len(entradas) == 2
    assert {e["accion_detallada"]["consolidada"] for e in entradas} == {True, False}


def test_tipo_sin_equivalencia_se_filtra_exacto(http, db_session, area):
    _, id_alerta = _alerta_con_humedad(db_session, http, area)
    assert _bitacora(http, "ALERTA_GENERADA", id_alerta)["total"] == 1
    assert _bitacora(http, "NO_EXISTE", id_alerta)["total"] == 0

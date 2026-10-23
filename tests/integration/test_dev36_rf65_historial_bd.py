# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | DEV-36 RF-65: 412 por config_version e historial desde el log de DB-14 |
"""DEV-36 contra PostgreSQL: dos ediciones con la misma config_version → la segunda 412,
y el historial lee el log append-only que llena el trigger de DB-14."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

pytestmark = pytest.mark.integration

TIPO = "MODELO_ESPECIES_GRANDES"


@pytest.fixture
def cliente(db_session, integration_app, monkeypatch):
    from src.prediction.infrastructure.routers.motor_ia_router import router
    from src.shared import jwt as jwt_module
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers

    monkeypatch.setattr(jwt_module, "_SECRET_KEY", "sgpmp-integration-tests-only")
    monkeypatch.setattr(jwt_module, "_EXPIRE_HOURS", 8)
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _cuerpo(**cambios):
    return {"tipo_modelo": TIPO, "ventana_temporal_min": 10, "modo_ejecucion": "SERVIDOR",
            "umbral_riesgo_alto": "0.70", "umbral_alerta_critica": "0.80", **cambios}


def test_segunda_edicion_con_la_misma_version_412_e_historial_append_only(
    cliente, db_session, crear_usuario_db, crear_auth_headers
):
    # Sin nodos Edge del tipo: el guardado no pasa por el broker.
    db_session.execute(text("DELETE FROM modulo4.configuraciones_motor_ia WHERE tipo_modelo = :t"), {"t": TIPO})
    headers = crear_auth_headers(crear_usuario_db(id_rol=1, estado=2))

    r = cliente.post("/prediccion/motor-ia", json=_cuerpo(), headers=headers)
    assert r.status_code == 201, r.text
    version = r.json()["config_version"]

    r = cliente.post("/prediccion/motor-ia", json=_cuerpo(ventana_temporal_min=12, config_version=version),
                     headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["config_version"] == version + 1

    r = cliente.post("/prediccion/motor-ia", json=_cuerpo(ventana_temporal_min=14, config_version=version),
                     headers=headers)
    assert r.status_code == 412, r.text
    assert r.json()["error_code"] == "CONFLICTO_CONCURRENCIA"

    r = cliente.get(f"/prediccion/motor-ia/{TIPO}/historial", headers=headers)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert [(i["config_version"], i["es_vigente"], i["operacion"]) for i in items] == [
        (version + 1, True, None), (version, False, "UPDATE"),
    ]
    assert items[0]["configuracion"]["ventana_temporal_min"] == 12
    assert items[1]["configuracion"]["ventana_temporal_min"] == 10

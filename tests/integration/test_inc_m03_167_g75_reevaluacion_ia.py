# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-167-G75 RF-57 E16: reevaluación por IA por HTTP con PostgreSQL real |
"""INC-M03-167-G75 (RF-57 E16, TC-M03-153/N15/N16): POST /iot/alertas/{id}/reevaluacion.

La alerta original se inserta con ``fecha_generacion`` en el pasado: el trigger de inmutabilidad
solo impide cambiarla después (UPDATE), que era lo que bloqueaba N16 en QA.
"""
from datetime import datetime, timedelta, timezone
import importlib
import json
import pkgutil

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from src.shared.database import get_db_sistema
from src.shared.error_handlers import register_error_handlers
from src.telemetry.infrastructure.routers import alerta_router

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def modelos():
    for paquete in ("src.configuration.infrastructure.models", "src.biological_assets.infrastructure.models",
                    "src.telemetry.infrastructure.models", "src.identity_access.infrastructure.models"):
        modulo = importlib.import_module(paquete)
        for item in pkgutil.iter_modules(modulo.__path__, paquete + "."):
            importlib.import_module(item.name)


@pytest.fixture(autouse=True)
def ventana_base(db_session):
    db_session.execute(text("DELETE FROM modulo4.parametros_mlops WHERE nombre_parametro='rf57_ventana_reevaluacion_min'"))
    db_session.commit()


@pytest.fixture
def client(db_session, headers_broker):
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(alerta_router.router)
    app.dependency_overrides[get_db_sistema] = lambda: db_session
    with TestClient(app, raise_server_exceptions=False, headers=headers_broker) as c:
        yield c


def _original(db, hace, tipo="ESTRES_TERMICO", severidad="LEVE", sin_motor=True):
    """Alerta generada con el motor caído (E3), ``hace`` tiempo."""
    generada = datetime.now(timezone.utc) - hace
    id_alerta = db.execute(text("""
        INSERT INTO modulo3.alertas(tipo_alerta,severidad,estado_alerta,origen_evento,tipo_variable,valor,unidad,
          fecha_evento,fecha_generacion,tiene_inferencia_no_disponible)
        VALUES (:tipo,:sev,'ACTIVA','EDGE','TEMPERATURA_AMBIENTAL',31,'°C',:gen,:gen,:sin_motor) RETURNING id_alerta
    """), {"tipo": tipo, "sev": severidad, "gen": generada, "sin_motor": sin_motor}).scalar_one()
    db.commit()
    return id_alerta


def _fila(db, id_alerta):
    return db.execute(text("SELECT to_jsonb(a) FROM modulo3.alertas a WHERE id_alerta=:id"), {"id": id_alerta}).scalar_one()


def _bitacora(db, tipo, id_alerta):
    return db.execute(text("SELECT count(*) FROM modulo3.bitacora_auditoria_iot WHERE tipo_evento=:t "
                           "AND entidad_afectada_id=:id"), {"t": tipo, "id": str(id_alerta)}).scalar_one()


def test_153_reevaluacion_que_difiere_crea_alerta_vinculada(client, db_session):
    original = _original(db_session, timedelta(minutes=10))
    antes = _fila(db_session, original)
    r = client.post(f"/iot/alertas/{original}/reevaluacion", json={"severidad_ia": "CRITICO", "probabilidad_ia": 0.91})
    assert r.status_code == 201, r.text
    assert r.json()["resultado"] == "ALERTA_GENERADA" and r.json()["id_alerta_original"] == original
    nueva = _fila(db_session, r.json()["id_alerta_nueva"])
    assert (nueva["origen_evento"], nueva["severidad"], nueva["tipo_alerta"]) == ("IA", "CRITICO", "ESTRES_TERMICO")
    assert nueva["referencia_alerta_original"] == original and nueva["tiene_generada_por_reevaluacion"] is True
    assert nueva["tiene_inferencia_no_disponible"] is False
    assert nueva["metadato_evento"]["reevaluacion"]["severidad_original"] == "LEVE"
    assert _fila(db_session, original) == antes  # la original no se modifica


def test_n15_reevaluacion_que_confirma_no_crea_alerta(client, db_session):
    original = _original(db_session, timedelta(minutes=10))
    r = client.post(f"/iot/alertas/{original}/reevaluacion", json={"severidad_ia": "LEVE"})
    assert r.status_code == 200, r.text
    assert (r.json()["resultado"], r.json()["id_alerta_nueva"]) == ("CONFIRMADA", None)
    assert db_session.execute(text("SELECT count(*) FROM modulo3.alertas WHERE referencia_alerta_original=:id"),
                              {"id": original}).scalar_one() == 0
    assert _bitacora(db_session, "REEVALUACION_CONFIRMADA", original) == 1


@pytest.mark.parametrize("hace,esperado", [(timedelta(minutes=59, seconds=59), 201),
                                           (timedelta(minutes=60, seconds=1), 422)])
def test_n16_ventana_de_60_minutos(client, db_session, hace, esperado):
    """El borde exacto 60:00 se prueba en la unitaria con reloj inyectado."""
    original = _original(db_session, hace)
    r = client.post(f"/iot/alertas/{original}/reevaluacion", json={"severidad_ia": "MODERADO"})
    assert r.status_code == esperado, r.text
    if esperado == 422:
        assert r.json()["error_code"] == "VENTANA_REEVALUACION_VENCIDA"
        assert _bitacora(db_session, "REEVALUACION_FUERA_DE_VENTANA", original) == 1


def test_ventana_configurada_por_el_administrador(client, db_session):
    db_session.execute(text("""
        INSERT INTO modulo4.parametros_mlops(nombre_parametro,valor_actual,valor_por_defecto,descripcion,rango_minimo)
        VALUES ('rf57_ventana_reevaluacion_min', CAST(:v AS jsonb), '60', 'G75', 1)
    """), {"v": json.dumps(90)})
    db_session.commit()
    original = _original(db_session, timedelta(minutes=75))
    assert client.post(f"/iot/alertas/{original}/reevaluacion", json={"severidad_ia": "MODERADO"}).status_code == 201


def test_segunda_reevaluacion_es_409(client, db_session):
    original = _original(db_session, timedelta(minutes=5))
    assert client.post(f"/iot/alertas/{original}/reevaluacion", json={"severidad_ia": "MODERADO"}).status_code == 201
    r = client.post(f"/iot/alertas/{original}/reevaluacion", json={"severidad_ia": "CRITICO"})
    assert r.status_code == 409 and r.json()["error_code"] == "REEVALUACION_YA_REGISTRADA", r.text


@pytest.mark.parametrize("datos", [{"sin_motor": False}, {"tipo": "TECNICA"}])
def test_alerta_que_no_admite_reevaluacion(client, db_session, datos):
    original = _original(db_session, timedelta(minutes=5), **datos)
    r = client.post(f"/iot/alertas/{original}/reevaluacion", json={"severidad_ia": "MODERADO"})
    assert r.status_code == 422 and r.json()["error_code"] == "REEVALUACION_NO_APLICA", r.text


def test_alerta_inexistente_y_token_ausente(client, db_session):
    assert client.post("/iot/alertas/999999999/reevaluacion", json={"severidad_ia": "LEVE"}).status_code == 404
    original = _original(db_session, timedelta(minutes=5))
    r = client.post(f"/iot/alertas/{original}/reevaluacion", json={"severidad_ia": "LEVE"},
                    headers={"Authorization": "Bearer otro"})
    assert r.status_code == 401

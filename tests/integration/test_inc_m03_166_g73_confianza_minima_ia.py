# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-166-G73 RF-57 CA-2: umbral mínimo de confianza de IA por HTTP |
"""INC-M03-166-G73 (RF-57 CA-2, TC-M03-G73): PREDICCION_PATOLOGIA solo con probabilidad ≥ umbral mínimo.

Router real y PostgreSQL real. Reproduce el caso de QA (probabilidad_ia = 0.74 creaba la alerta).
"""
from datetime import datetime, timedelta, timezone
import importlib
import json
import pkgutil
from uuid import uuid4

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


@pytest.fixture
def hw(db_session):
    tag = uuid4().hex[:12]
    nombre = "Gsetentaytres " + "".join(chr(97 + int(c, 16)) for c in tag)
    area = db_session.execute(text("""
        WITH finca AS (
            INSERT INTO modulo9.fincas(nombre,ubicacion,tamano_h,es_activo,fecha_creacion,fecha_actualizacion)
            VALUES (:nombre,'{}',10,true,now(),now()) RETURNING id_finca)
        INSERT INTO modulo9.infraestructuras(nombre,id_finca,superficie,es_activo,tipo)
        SELECT :nombre,id_finca,100,true,'Estanque' FROM finca RETURNING id_infraestructura
    """), {"nombre": nombre}).scalar_one()
    device = db_session.execute(text("""
        INSERT INTO modulo9.dispositivos_iot(serial,descripcion,es_activo,fecha_creacion,id_infraestructura,id_tipo_dispositivo)
        VALUES (:serial,'G73',true,now(),:area,3) RETURNING id_dispositivo_iot
    """), {"serial": tag, "area": area}).scalar_one()
    sensor = db_session.execute(text("""
        INSERT INTO modulo9.sensores(id_dispositivo_iot,es_activo,nombre)
        VALUES (:device,true,'Sensor G73') RETURNING id_sensores
    """), {"device": device}).scalar_one()
    db_session.commit()
    return {"device": device, "sensor": sensor, "serial": tag}


@pytest.fixture
def client(db_session, headers_broker):
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(alerta_router.router)
    app.dependency_overrides[get_db_sistema] = lambda: db_session
    with TestClient(app, raise_server_exceptions=False, headers=headers_broker) as c:
        yield c


def _prediccion(client, db, hw, probabilidad, severidad_ia="LEVE"):
    id_lectura = db.execute(text("""
        INSERT INTO modulo3.telemetrias(id_sensor,id_variable,id_dispositivo_iot,valor_crudo,
          timestamp_captura,timestamp_procesamiento,origen,estado_calidad,metadatos,categoria_variable,unidad_medida)
        VALUES (:s,9,:d,31,:captura,now(),'TIEMPO_REAL','LECTURA_VALIDA','{}','AMBIENTAL','°C') RETURNING id_telemetria
    """), {"s": hw["sensor"], "d": hw["device"], "captura": datetime.now(timezone.utc) - timedelta(minutes=1)}).scalar_one()
    db.commit()
    return client.post("/iot/alertas", json={
        "device_id": hw["device"], "sensor_id": hw["sensor"], "serial": hw["serial"],
        "tipo_variable": "TEMPERATURA_AMBIENTAL", "valor": "31", "unidad": "°C",
        "timestamp_evento": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        "estado_dato": "LECTURA_VALIDA", "severidad_edge": "LEVE", "origen_evento": "IA",
        "tipo_alerta_ia": "PREDICCION_PATOLOGIA", "severidad_ia": severidad_ia,
        "probabilidad_ia": probabilidad, "id_telemetria": id_lectura})


def _alertas(db, hw):
    return db.execute(text("SELECT count(*) FROM modulo3.alertas WHERE id_sensor=:s"), {"s": hw["sensor"]}).scalar_one()


def _umbral(db, valor):
    db.execute(text("DELETE FROM modulo4.parametros_mlops WHERE nombre_parametro='rf57_umbral_confianza_minimo'"))
    db.execute(text("""
        INSERT INTO modulo4.parametros_mlops(nombre_parametro,valor_actual,valor_por_defecto,descripcion,rango_minimo,rango_maximo)
        VALUES ('rf57_umbral_confianza_minimo', CAST(:v AS jsonb), '0.75', 'G73', 0, 1)
    """), {"v": json.dumps(valor)})
    db.commit()


@pytest.fixture(autouse=True)
def sin_umbral_configurado(db_session):
    db_session.execute(text("DELETE FROM modulo4.parametros_mlops WHERE nombre_parametro='rf57_umbral_confianza_minimo'"))
    db_session.commit()


def test_prediccion_bajo_el_valor_base_no_genera_alerta(client, db_session, hw):
    """Caso de QA: 0.74 con el valor base 0.75 (sin configurar)."""
    r = _prediccion(client, db_session, hw, 0.74)
    assert r.status_code == 201, r.text
    assert r.json()["id_alerta"] is None and "umbral mínimo de confianza 0.75" in r.json()["motivo_descarte"]
    assert _alertas(db_session, hw) == 0
    evento = db_session.execute(text(
        "SELECT accion_detallada FROM modulo3.bitacora_auditoria_iot WHERE tipo_evento='PREDICCION_BAJO_UMBRAL_CONFIANZA' "
        "AND entidad_afectada_id=:d"), {"d": str(hw["device"])}).scalar_one()
    assert evento["probabilidad_ia"] == "0.74" and evento["umbral_confianza_minimo"] == "0.75"


@pytest.mark.parametrize("probabilidad,severidad", [(0.75, "LEVE"), (0.85, "MODERADO"), (0.95, "CRITICO")])
def test_prediccion_en_o_sobre_el_umbral_genera_alerta(client, db_session, hw, probabilidad, severidad):
    r = _prediccion(client, db_session, hw, probabilidad)
    assert r.status_code == 201, r.text
    assert (r.json()["tipo_alerta"], r.json()["severidad"]) == ("PREDICCION_PATOLOGIA", severidad)


def test_umbral_configurado_prevalece_sobre_el_valor_base(client, db_session, hw):
    _umbral(db_session, 0.80)
    assert _prediccion(client, db_session, hw, 0.78).json()["id_alerta"] is None
    r = _prediccion(client, db_session, hw, 0.80)
    assert r.json()["tipo_alerta"] == "PREDICCION_PATOLOGIA", r.text


def test_umbral_configurado_invalido_falla_expresamente(client, db_session, hw):
    _umbral(db_session, "alto")
    r = _prediccion(client, db_session, hw, 0.90)
    assert r.status_code == 503 and r.json()["error_code"] == "PARAMETRO_CONFIGURACION_INVALIDO", r.text
    assert _alertas(db_session, hw) == 0

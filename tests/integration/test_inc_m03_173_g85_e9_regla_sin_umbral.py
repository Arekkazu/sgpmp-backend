# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-173-G85 RF-57 E9: evento sin umbral configurado por HTTP con PostgreSQL real |
"""INC-M03-173-G85 (RF-57 E9, TC-M03-G85): variable sin umbrales configurados (RF-17).

Router real, adaptadores reales y PostgreSQL real. Sin umbral para la variable en las especies del área:
no hay alerta operativa, queda ERROR_CONFIGURACION_REGLA en la bitácora y una alerta técnica para el
Administrador, con el evento conservado como PENDIENTE_EVALUACION.
"""
from datetime import datetime, timedelta, timezone
import importlib
import pkgutil
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from src.shared.database import get_db, get_db_sistema
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
def http(db_session, crear_usuario_db, crear_auth_headers, monkeypatch, headers_broker):
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
    app.dependency_overrides[get_db_sistema] = sesion
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, admin, headers_broker


@pytest.fixture
def area(db_session):
    def crear(con_especie=True):
        tag = uuid4().hex[:12]
        nombre = "Gochentaycinco " + "".join(chr(97 + int(c, 16)) for c in tag)
        id_area = db_session.execute(text("""WITH finca AS (
            INSERT INTO modulo9.fincas(nombre,ubicacion,tamano_h,es_activo,fecha_creacion,fecha_actualizacion)
            VALUES (:n,'{}',10,true,now(),now()) RETURNING id_finca)
            INSERT INTO modulo9.infraestructuras(nombre,id_finca,superficie,es_activo,tipo)
            SELECT :n,id_finca,100,true,'Estanque' FROM finca RETURNING id_infraestructura"""), {"n": nombre}).scalar_one()
        device = db_session.execute(text("""INSERT INTO modulo9.dispositivos_iot(serial,descripcion,es_activo,
            fecha_creacion,id_infraestructura,id_tipo_dispositivo) VALUES (:s,'G85',true,now(),:a,3)
            RETURNING id_dispositivo_iot"""), {"s": tag, "a": id_area}).scalar_one()
        sensor = db_session.execute(text("INSERT INTO modulo9.sensores(id_dispositivo_iot,es_activo,nombre) "
                                         "VALUES (:d,true,'G85') RETURNING id_sensores"), {"d": device}).scalar_one()
        especie = db_session.execute(text("SELECT min(id_especie) FROM modulo9.especies WHERE es_activo")).scalar_one()
        if con_especie:
            db_session.execute(text("INSERT INTO modulo9.infraestructuras_especies(id_infraestructura,id_especie) "
                                    "VALUES (:a,:e)"), {"a": id_area, "e": especie})
        db_session.commit()
        return {"area": id_area, "device": device, "sensor": sensor, "serial": tag, "especie": especie}
    return crear


def _variable(db, codigo):
    return db.execute(text("SELECT id_variable_ambiental FROM modulo9.variables_ambientales WHERE codigo_telemetria=:c"),
                      {"c": codigo}).scalar_one()


def _umbral(db, especie, codigo):
    db.execute(text("""INSERT INTO modulo9.umbrales_ambientales(nombre,unidad_medida,es_activo,id_especie,
        id_variable_ambiental,valor_min,valor_max) VALUES ('G85','u',true,:e,:v,0,10)"""),
               {"e": especie, "v": _variable(db, codigo)})
    db.commit()


def _evento(http, db, hw, codigo="NH3", valor="25", unidad="ppm"):
    client, _, broker = http
    id_lectura = db.execute(text("""INSERT INTO modulo3.telemetrias(id_sensor,id_variable,id_dispositivo_iot,valor_crudo,
        timestamp_captura,timestamp_procesamiento,origen,estado_calidad,metadatos,categoria_variable,unidad_medida)
        VALUES (:s,:v,:d,:val,clock_timestamp() - interval '1 minute',now(),'TIEMPO_REAL','LECTURA_VALIDA','{}','AMBIENTAL',:u)
        RETURNING id_telemetria"""), {"s": hw["sensor"], "v": _variable(db, codigo), "d": hw["device"],
                                      "val": valor, "u": unidad}).scalar_one()
    db.commit()
    return client.post("/iot/alertas", headers=broker, json={
        "device_id": hw["device"], "sensor_id": hw["sensor"], "serial": hw["serial"], "tipo_variable": codigo,
        "valor": valor, "unidad": unidad, "timestamp_evento": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        "estado_dato": "LECTURA_VALIDA", "severidad_edge": "LEVE", "origen_evento": "EDGE", "id_telemetria": id_lectura})


def _fila(db, id_alerta):
    return db.execute(text("SELECT to_jsonb(a) FROM modulo3.alertas a WHERE id_alerta=:id"), {"id": id_alerta}).scalar_one()


def _bitacora(db, hw):
    return db.execute(text("SELECT accion_detallada FROM modulo3.bitacora_auditoria_iot WHERE "
                           "tipo_evento='ERROR_CONFIGURACION_REGLA' AND entidad_afectada_id=:d ORDER BY id_evento"),
                      {"d": str(hw["device"])}).scalars().all()


def test_g85_01_sin_umbral_no_hay_alerta_operativa_y_el_evento_queda_pendiente(http, db_session, area):
    hw = area()
    r = _evento(http, db_session, hw)
    assert r.status_code == 201, r.text
    assert r.json()["tipo_alerta"] == "TECNICA" and "PENDIENTE_EVALUACION" in r.json()["motivo_descarte"]
    tecnica = _fila(db_session, r.json()["id_alerta"])
    assert tecnica["tipo_variable"] == "ERROR_CONFIGURACION_REGLA"
    pendiente = tecnica["metadato_evento"]["evento_pendiente"]
    assert pendiente["estado_evaluacion"] == "PENDIENTE_EVALUACION" and pendiente["tipo_variable"] == "NH3"
    assert tecnica["metadato_evento"]["e9"]["motivo"] == "SIN_UMBRAL_PARA_LAS_ESPECIES"
    client, admin, _ = http
    assert client.get("/iot/alertas", headers=admin, params={"id_sensor": hw["sensor"]}).json()["items"] == []


def test_g85_02_queda_error_configuracion_regla_en_la_bitacora(http, db_session, area):
    hw = area()
    _evento(http, db_session, hw)
    entrada, = _bitacora(db_session, hw)
    assert entrada["evento"]["estado_evaluacion"] == "PENDIENTE_EVALUACION" and entrada["evento"]["valor"] == "25"


def test_g85_03_el_administrador_ve_la_alerta_tecnica(http, db_session, area):
    hw = area()
    id_alerta = _evento(http, db_session, hw).json()["id_alerta"]
    client, admin, _ = http
    tecnicas = client.get("/iot/alertas-tecnicas", headers=admin, params={"por_pagina": 200}).json()["items"]
    assert id_alerta in [a["id_alerta"] for a in tecnicas]


def test_eventos_siguientes_del_sensor_se_consolidan_y_no_se_pierden(http, db_session, area):
    hw = area()
    primero = _evento(http, db_session, hw).json()
    segundo = _evento(http, db_session, hw, valor="30").json()
    assert segundo["es_duplicado"] and segundo["alerta_existente_id"] == primero["id_alerta"]
    assert _fila(db_session, primero["id_alerta"])["frecuencia_evento"] == 2
    assert sorted(e["evento"]["valor"] for e in _bitacora(db_session, hw)) == ["25", "30"]  # ninguno se pierde


def test_area_sin_especies_tambien_es_e9(http, db_session, area):
    hw = area(con_especie=False)
    r = _evento(http, db_session, hw)
    assert _fila(db_session, r.json()["id_alerta"])["metadato_evento"]["e9"]["motivo"] == "AREA_SIN_ESPECIES"


def test_con_umbral_configurado_la_alerta_es_operativa(http, db_session, area):
    hw = area()
    _umbral(db_session, hw["especie"], "NH3")
    r = _evento(http, db_session, hw)
    assert r.status_code == 201 and r.json()["tipo_alerta"] == "SINDROME_RESPIRATORIO", r.text
    assert _bitacora(db_session, hw) == []

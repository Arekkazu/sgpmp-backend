# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-168-G76 RF-57: E12/E13 sin parámetro cargado y configuración por API |
# | 2026-10-28 | Arekkazu | INC-M03-168-G76 RF-57: el evento trae el THI que exigen G68/G70 |
# | 2026-10-28 | Arekkazu | INC-M03-173-G85 RF-57 E9: el área de la prueba tiene umbrales RF-17 |
"""INC-M03-168-G76 (RF-57 E12/E13, TC-M03-142/143/N18).

Sin `umbral_confianza_edge_ia` en la BD (como en TEST) los conflictos Edge/IA respondían 503. Ahora
se resuelven con el valor base del RF (0.85), y el administrador lo cambia por
PATCH /configuracion/parametros-alertas.
"""
from datetime import datetime, timedelta, timezone
import importlib
import pkgutil
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from src.configuration.infrastructure.routers import parametros_alertas_router
from src.shared.database import get_db, get_db_sistema
from src.shared.error_handlers import register_error_handlers
from src.telemetry.infrastructure.routers import alerta_router
from tests.integration.conftest import sembrar_umbrales_rf17

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def modelos():
    for paquete in ("src.configuration.infrastructure.models", "src.biological_assets.infrastructure.models",
                    "src.telemetry.infrastructure.models", "src.identity_access.infrastructure.models"):
        modulo = importlib.import_module(paquete)
        for item in pkgutil.iter_modules(modulo.__path__, paquete + "."):
            importlib.import_module(item.name)


@pytest.fixture(autouse=True)
def sin_umbral(db_session):
    db_session.execute(text("DELETE FROM modulo4.parametros_mlops WHERE nombre_parametro='umbral_confianza_edge_ia'"))
    db_session.commit()


@pytest.fixture
def http(db_session, crear_usuario_db, crear_auth_headers, monkeypatch, headers_broker):
    from src.shared import jwt as jwt_module
    monkeypatch.setattr(jwt_module, "_SECRET_KEY", "sgpmp-integration-tests-only")
    rol = lambda n: db_session.execute(text("SELECT id_rol FROM modulo1.roles WHERE nombre_rol=:n"), {"n": n}).scalar_one()
    usuarios = {"admin": crear_auth_headers(crear_usuario_db(id_rol=rol("Administrador"))),
                "vet": crear_auth_headers(crear_usuario_db(id_rol=rol("Veterinario")))}
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(alerta_router.router)
    app.include_router(parametros_alertas_router.router)

    def sesion():
        db_session.info.clear()
        return db_session

    app.dependency_overrides[get_db] = sesion
    app.dependency_overrides[get_db_sistema] = sesion
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, usuarios, headers_broker


def _sensor(db):
    tag = uuid4().hex[:12]
    nombre = "Gsetentayseis " + "".join(chr(97 + int(c, 16)) for c in tag)
    area = db.execute(text("""
        WITH finca AS (
            INSERT INTO modulo9.fincas(nombre,ubicacion,tamano_h,es_activo,fecha_creacion,fecha_actualizacion)
            VALUES (:n,'{}',10,true,now(),now()) RETURNING id_finca)
        INSERT INTO modulo9.infraestructuras(nombre,id_finca,superficie,es_activo,tipo)
        SELECT :n,id_finca,100,true,'Estanque' FROM finca RETURNING id_infraestructura"""), {"n": nombre}).scalar_one()
    device = db.execute(text("""
        INSERT INTO modulo9.dispositivos_iot(serial,descripcion,es_activo,fecha_creacion,id_infraestructura,id_tipo_dispositivo)
        VALUES (:s,'G76',true,now(),:a,3) RETURNING id_dispositivo_iot"""), {"s": tag, "a": area}).scalar_one()
    sembrar_umbrales_rf17(db, area)
    sensor = db.execute(text("INSERT INTO modulo9.sensores(id_dispositivo_iot,es_activo,nombre) VALUES (:d,true,'G76') "
                             "RETURNING id_sensores"), {"d": device}).scalar_one()
    db.commit()
    return {"device": device, "sensor": sensor, "serial": tag}


def _conflicto(http, db, sev_edge, sev_ia, prob, tipo_ia=None):
    client, _, broker = http
    hw = _sensor(db)
    id_lectura = db.execute(text("""
        INSERT INTO modulo3.telemetrias(id_sensor,id_variable,id_dispositivo_iot,valor_crudo,timestamp_captura,
          timestamp_procesamiento,origen,estado_calidad,metadatos,categoria_variable,unidad_medida)
        VALUES (:s,9,:d,31,now(),now(),'TIEMPO_REAL','LECTURA_VALIDA','{}','AMBIENTAL','°C') RETURNING id_telemetria
    """), {"s": hw["sensor"], "d": hw["device"]}).scalar_one()
    db.commit()
    cuerpo = {"device_id": hw["device"], "sensor_id": hw["sensor"], "serial": hw["serial"],
              "tipo_variable": "TEMPERATURA_AMBIENTAL", "valor": "31", "unidad": "°C",
              "timestamp_evento": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
              "estado_dato": "LECTURA_VALIDA", "severidad_edge": sev_edge, "origen_evento": "EDGE",
              "severidad_ia": sev_ia, "probabilidad_ia": prob, "id_telemetria": id_lectura,
              # G68/G70 (#822/#823): la severidad Edge sale del valor y ESTRES_TERMICO exige el THI;
              # con 31 °C (banda LEVE) el THI fija la severidad Edge de cada caso.
              "correlacion_variables": {"THI": {"LEVE": "75", "MODERADO": "80", "CRITICO": "85"}[sev_edge]}}
    if tipo_ia:
        cuerpo["tipo_alerta_ia"] = tipo_ia
    r = client.post("/iot/alertas", headers=broker, json=cuerpo)
    assert r.status_code == 201, r.text
    return db.execute(text("SELECT tipo_alerta::text, severidad::text, conflicto_resolucion::text FROM modulo3.alertas "
                           "WHERE id_alerta=:id"), {"id": r.json()["id_alerta"]}).one()


@pytest.mark.parametrize("sev_edge,sev_ia,prob,esperado", [
    ("LEVE", "CRITICO", 0.84, ("ESTRES_TERMICO", "MODERADO", "SEVERIDAD_COMPROMISO")),
    ("LEVE", "CRITICO", 0.85, ("ESTRES_TERMICO", "CRITICO", "SEVERIDAD_MAXIMA")),
    ("MODERADO", "CRITICO", 0.80, ("ESTRES_TERMICO", "CRITICO", "SEVERIDAD_MAXIMA")),
    ("CRITICO", "LEVE", 0.50, ("ESTRES_TERMICO", "CRITICO", "SEVERIDAD_MAXIMA")),
])
def test_142_conflicto_de_severidad_sin_parametro_cargado(http, db_session, sev_edge, sev_ia, prob, esperado):
    assert tuple(_conflicto(http, db_session, sev_edge, sev_ia, prob)) == esperado


@pytest.mark.parametrize("prob,esperado", [(0.84, ("ESTRES_TERMICO", "EDGE_PREVALECE")),
                                           (0.85, ("SINDROME_RESPIRATORIO", "IA_PREVALECE")),
                                           (0.86, ("SINDROME_RESPIRATORIO", "IA_PREVALECE"))])
def test_143_conflicto_de_tipo_sin_parametro_cargado(http, db_session, prob, esperado):
    tipo, _, resolucion = _conflicto(http, db_session, "MODERADO", "MODERADO", prob, tipo_ia="SINDROME_RESPIRATORIO")
    assert (tipo, resolucion) == esperado


def test_n18_el_administrador_consulta_y_cambia_el_umbral_por_api(http, db_session):
    client, usuarios, _ = http
    antes = {p["nombre"]: p for p in client.get("/configuracion/parametros-alertas", headers=usuarios["admin"]).json()}
    assert (antes["umbral_confianza_edge_ia"]["fuente"], float(antes["umbral_confianza_edge_ia"]["valor"])) == ("VALOR_BASE", 0.85)

    r = client.patch("/configuracion/parametros-alertas", headers=usuarios["admin"],
                     json={"parametros": {"umbral_confianza_edge_ia": 0.80}})
    assert r.status_code == 200, r.text
    despues = {p["nombre"]: p for p in r.json()}
    assert (despues["umbral_confianza_edge_ia"]["fuente"], despues["umbral_confianza_edge_ia"]["valor"]) == ("CONFIGURADO", 0.8)
    assert db_session.execute(text("SELECT id_usuario_modificador FROM modulo4.parametros_mlops "
                                   "WHERE nombre_parametro='umbral_confianza_edge_ia'")).scalar_one() is not None

    # Con 0.80, una confianza de 0.82 ya hace prevalecer a la IA (con 0.85 prevalecía el Edge).
    tipo, _, resolucion = _conflicto(http, db_session, "MODERADO", "MODERADO", 0.82, tipo_ia="SINDROME_RESPIRATORIO")
    assert (tipo, resolucion) == ("SINDROME_RESPIRATORIO", "IA_PREVALECE")


@pytest.mark.parametrize("parametros", [{"umbral_confianza_edge_ia": 0.60}, {"umbral_confianza_edge_ia": 0.96},
                                        {"rf62_k": 3}])
def test_n18_valores_fuera_de_rango_o_ajenos_son_400(http, parametros):
    client, usuarios, _ = http
    r = client.patch("/configuracion/parametros-alertas", headers=usuarios["admin"], json={"parametros": parametros})
    assert r.status_code == 400, r.text


def test_solo_el_administrador_cambia_el_umbral(http):
    client, usuarios, _ = http
    r = client.patch("/configuracion/parametros-alertas", headers=usuarios["vet"],
                     json={"parametros": {"umbral_confianza_edge_ia": 0.80}})
    assert r.status_code == 403, r.text
    assert client.patch("/configuracion/parametros-alertas", json={"parametros": {}}).status_code == 401

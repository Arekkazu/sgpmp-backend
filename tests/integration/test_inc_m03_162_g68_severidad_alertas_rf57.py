# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-162-G68 RF-57: severidad por valor, FALLO_AMBIENTAL técnica y escalada THI por HTTP |
# | 2026-10-28 | destroyerban | INC-M03-163-G70 RF-57: los casos de severidad envían la condición mínima de su compuesta |
# | 2026-10-28 | destroyerban | INC-M03-164-G71 RF-57 E14: la lectura de prueba usa la variable del evento |
# | 2026-10-28 | Arekkazu | INC-M03-173-G85 RF-57 E9: el área de la prueba tiene umbrales RF-17 |
"""INC-M03-162-G68 (RF-57 Fase 5, TC-M03-G68/G69/G72): POST /iot/alertas evalúa el valor.

Router real, adaptadores reales de M09 y PostgreSQL real. Reproduce los casos de QA:
- G68: lectura fuera del rango absoluto del sensor o con error de calibración → alerta
  técnica FALLO_AMBIENTAL (visible en /iot/alertas-tecnicas, no en /iot/alertas).
- G69: la severidad sale de las bandas base de RF-57, no de ``severidad_edge``; la banda
  NORMAL no genera alerta.
- G72: ESTRES_TERMICO sube un nivel con THI ≥ LEVE y temperatura corporal > 40 °C o
  frecuencia respiratoria en rango MODERADO.
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
from tests.integration.conftest import sembrar_umbrales_rf17

pytestmark = pytest.mark.integration

_UNIDAD = {"TEMPERATURA_AMBIENTAL": "°C", "HUMEDAD_RELATIVA": "%", "OXIGENO_DISUELTO": "mg/L",
           "FRECUENCIA_RESPIRATORIA": "rpm"}


@pytest.fixture(autouse=True)
def modelos():
    for paquete in ("src.configuration.infrastructure.models", "src.biological_assets.infrastructure.models",
                    "src.telemetry.infrastructure.models", "src.identity_access.infrastructure.models"):
        modulo = importlib.import_module(paquete)
        for item in pkgutil.iter_modules(modulo.__path__, paquete + "."):
            importlib.import_module(item.name)


@pytest.fixture
def nuevo_sensor(db_session):
    """Un sensor por caso: la deduplicación de RF-57 es por sensor y variable."""
    def crear():
        tag = uuid4().hex[:12]
        nombre = "Gsesentayocho " + "".join(chr(97 + int(c, 16)) for c in tag)
        area = db_session.execute(text("""
            WITH finca AS (
                INSERT INTO modulo9.fincas(nombre,ubicacion,tamano_h,es_activo,fecha_creacion,fecha_actualizacion)
                VALUES (:nombre,'{}',10,true,now(),now()) RETURNING id_finca)
            INSERT INTO modulo9.infraestructuras(nombre,id_finca,superficie,es_activo,tipo)
            SELECT :nombre,id_finca,100,true,'Estanque' FROM finca RETURNING id_infraestructura
        """), {"nombre": nombre}).scalar_one()
        device = db_session.execute(text("""
            INSERT INTO modulo9.dispositivos_iot(serial,descripcion,es_activo,fecha_creacion,id_infraestructura,id_tipo_dispositivo)
            VALUES (:serial,'G68',true,now(),:area,3) RETURNING id_dispositivo_iot
        """), {"serial": tag, "area": area}).scalar_one()
        sembrar_umbrales_rf17(db_session, area)
        sensor = db_session.execute(text("""
            INSERT INTO modulo9.sensores(id_dispositivo_iot,es_activo,nombre)
            VALUES (:device,true,'Sensor G68') RETURNING id_sensores
        """), {"device": device}).scalar_one()
        db_session.commit()
        return {"device": device, "sensor": sensor, "serial": tag}
    return crear


@pytest.fixture
def http(db_session, crear_usuario_db, crear_auth_headers, monkeypatch, headers_broker):
    from src.shared import jwt as jwt_module
    monkeypatch.setattr(jwt_module, "_SECRET_KEY", "sgpmp-integration-tests-only")
    rol_admin = db_session.execute(text("SELECT id_rol FROM modulo1.roles WHERE nombre_rol='Administrador'")).scalar_one()
    admin = crear_auth_headers(crear_usuario_db(id_rol=rol_admin))
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
        yield client, admin, headers_broker, db_session


def _lectura(db, hw, valor, estado, variable="TEMPERATURA_AMBIENTAL"):
    # G71: la lectura es de la variable del evento (E14 busca compañeras por variable en el área).
    id_variable = db.execute(text("SELECT id_variable_ambiental FROM modulo9.variables_ambientales "
                                  "WHERE codigo_telemetria=:c"), {"c": variable}).scalar_one()
    id_lectura = db.execute(text("""
        INSERT INTO modulo3.telemetrias(id_sensor,id_variable,id_dispositivo_iot,valor_crudo,
          timestamp_captura,timestamp_procesamiento,origen,estado_calidad,metadatos,categoria_variable,unidad_medida)
        VALUES (:s,:var,:d,:v,:captura,now(),'TIEMPO_REAL',:estado,'{}','AMBIENTAL','°C') RETURNING id_telemetria
    """), {"s": hw["sensor"], "var": id_variable, "d": hw["device"], "v": valor, "estado": estado,
           "captura": datetime.now(timezone.utc) - timedelta(minutes=1)}).scalar_one()
    db.commit()
    return id_lectura


def _enviar(http, hw, tipo_variable, valor, severidad, estado="LECTURA_VALIDA", correlacion=None):
    client, _, broker, db = http
    cuerpo = {"device_id": hw["device"], "sensor_id": hw["sensor"], "serial": hw["serial"],
              "tipo_variable": tipo_variable, "valor": str(valor), "unidad": _UNIDAD[tipo_variable],
              "timestamp_evento": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
              "estado_dato": estado, "severidad_edge": severidad, "origen_evento": "EDGE",
              "id_telemetria": _lectura(db, hw, valor, estado, tipo_variable), "metadata_evento": {"caso": "G68"}}
    if correlacion is not None:
        cuerpo["correlacion_variables"] = correlacion
    respuesta = client.post("/iot/alertas", headers=broker, json=cuerpo)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _alerta(db, id_alerta):
    return db.execute(text("SELECT to_jsonb(a) FROM modulo3.alertas a WHERE id_alerta=:id"), {"id": id_alerta}).scalar_one()


# ---------------------------------------------------------------- TC-M03-G68: FALLO_AMBIENTAL

@pytest.mark.parametrize("valor,severidad", [("200", "CRITICO"), ("250", "MODERADO")])
def test_valor_fuera_del_rango_absoluto_genera_fallo_ambiental_tecnico(db_session, http, nuevo_sensor, valor, severidad):
    hw = nuevo_sensor()
    r = _enviar(http, hw, "TEMPERATURA_AMBIENTAL", valor, severidad)
    assert (r["tipo_alerta"], r["severidad"]) == ("TECNICA", "MODERADO")
    fila = _alerta(db_session, r["id_alerta"])
    assert fila["tipo_variable"] == "FALLO_AMBIENTAL"
    assert fila["metadato_evento"]["causa"] == "VALOR_FUERA_DE_RANGO_ABSOLUTO"
    assert fila["metadato_evento"]["rango_fisico"]["max"] == "100"
    client, admin, _, _ = http
    tecnicas = client.get("/iot/alertas-tecnicas", headers=admin, params={"por_pagina": 200}).json()["items"]
    operativas = client.get("/iot/alertas", headers=admin, params={"id_sensor": hw["sensor"]}).json()["items"]
    assert r["id_alerta"] in [a["id_alerta"] for a in tecnicas]
    assert operativas == []


def test_fallo_ambiental_de_variable_critica_es_critico(db_session, http, nuevo_sensor):
    db_session.execute(text("UPDATE modulo9.variables_ambientales SET es_critica = true "
                            "WHERE codigo_telemetria = 'TEMPERATURA_AMBIENTAL'"))
    db_session.commit()
    r = _enviar(http, nuevo_sensor(), "TEMPERATURA_AMBIENTAL", "200", "LEVE")
    assert (r["tipo_alerta"], r["severidad"]) == ("TECNICA", "CRITICO")


def test_error_de_calibracion_genera_fallo_ambiental_tecnico(db_session, http, nuevo_sensor):
    r = _enviar(http, nuevo_sensor(), "TEMPERATURA_AMBIENTAL", "25", "CRITICO", estado="ERROR_CALIBRACION")
    assert (r["tipo_alerta"], r["severidad"]) == ("TECNICA", "MODERADO")
    assert _alerta(db_session, r["id_alerta"])["metadato_evento"]["causa"] == "ERROR_CALIBRACION"


def test_fallo_ambiental_repetido_se_consolida(db_session, http, nuevo_sensor):
    hw = nuevo_sensor()
    primero = _enviar(http, hw, "TEMPERATURA_AMBIENTAL", "200", "CRITICO")
    segundo = _enviar(http, hw, "TEMPERATURA_AMBIENTAL", "210", "CRITICO")
    assert segundo["es_duplicado"] and segundo["alerta_existente_id"] == primero["id_alerta"]
    assert _alerta(db_session, primero["id_alerta"])["frecuencia_evento"] == 2


# ---------------------------------------------------------------- TC-M03-G69: severidad por bandas

@pytest.mark.parametrize("variable,valor,declarada,esperada", [
    ("TEMPERATURA_AMBIENTAL", "36.1", "LEVE", "CRITICO"),
    ("TEMPERATURA_AMBIENTAL", "33.1", "CRITICO", "MODERADO"),
    ("TEMPERATURA_AMBIENTAL", "36.0", "CRITICO", "MODERADO"),
    ("TEMPERATURA_AMBIENTAL", "30.1", "CRITICO", "LEVE"),
    ("HUMEDAD_RELATIVA", "95", "LEVE", "CRITICO"),
    ("OXIGENO_DISUELTO", "2.5", "LEVE", "MODERADO"),
])
def test_severidad_sale_del_valor_no_de_la_declarada(db_session, http, nuevo_sensor, variable, valor, declarada, esperada):
    # G70: cada compuesta lleva su condición mínima (THI LEVE para ESTRES_TERMICO, pH LEVE para RIESGO_HIDRICO).
    correlacion = {"OXIGENO_DISUELTO": {"PH_AGUA": 6.4}}.get(variable, {"THI": 72.5})
    r = _enviar(http, nuevo_sensor(), variable, valor, declarada, correlacion=correlacion)
    assert r["severidad"] == esperada
    fila = _alerta(db_session, r["id_alerta"])
    assert fila["severidad"] == esperada
    assert fila["metadato_evento"]["evaluacion_rf57"]["severidad_reportada"] == declarada
    assert fila["severidad_edge_original"] == (declarada if declarada != esperada else None)
    sla = {"CRITICO": 5, "MODERADO": 30, "LEVE": 120}[esperada]
    vence = datetime.fromisoformat(fila["fecha_vencimiento"]) - datetime.fromisoformat(fila["fecha_generacion"])
    assert vence == timedelta(minutes=sla)


@pytest.mark.parametrize("variable,valor,declarada", [
    ("TEMPERATURA_AMBIENTAL", "25.0", "CRITICO"),
    ("TEMPERATURA_AMBIENTAL", "30.0", "MODERADO"),
    ("HUMEDAD_RELATIVA", "60.0", "MODERADO"),
    ("OXIGENO_DISUELTO", "8.0", "CRITICO"),
])
def test_valor_en_banda_normal_no_genera_alerta(db_session, http, nuevo_sensor, variable, valor, declarada):
    hw = nuevo_sensor()
    r = _enviar(http, hw, variable, valor, declarada)
    assert r["id_alerta"] is None and "banda NORMAL" in r["motivo_descarte"]
    assert db_session.execute(text("SELECT count(*) FROM modulo3.alertas WHERE id_sensor=:s"),
                              {"s": hw["sensor"]}).scalar_one() == 0
    assert db_session.execute(text(
        "SELECT count(*) FROM modulo3.bitacora_auditoria_iot WHERE tipo_evento='EVENTO_SIN_DESVIACION_RF57' "
        "AND accion_detallada->>'id_sensor' = :s"), {"s": str(hw["sensor"])}).scalar_one() == 1


def test_variable_con_banda_por_especie_conserva_la_severidad_declarada(http, nuevo_sensor):
    r = _enviar(http, nuevo_sensor(), "FRECUENCIA_RESPIRATORIA", "50", "MODERADO")
    assert r["severidad"] == "MODERADO"


# ---------------------------------------------------------------- TC-M03-G72: escalada de ESTRES_TERMICO

@pytest.mark.parametrize("valor,declarada,correlacion,esperada,escala", [
    ("30.5", "LEVE", {"THI": 72.12, "temperatura_corporal": 40.5}, "MODERADO", True),
    ("31", "MODERADO", {"THI": 79.14, "TEMP_CORPORAL": {"valor": 40.8}}, "CRITICO", True),
    ("31", "LEVE", {"THI": "79.14", "FRECUENCIA_RESPIRATORIA": {"severidad": "MODERADO"}}, "CRITICO", True),
    ("30.5", "LEVE", {"THI": 72.12}, "LEVE", False),
    ("30.5", "LEVE", {"THI": 72.12, "temperatura_corporal": 39.9}, "LEVE", False),
    ("37", "CRITICO", {"THI": 85, "temperatura_corporal": 41}, "CRITICO", True),  # ya en el tope
])
def test_estres_termico_escala_con_variables_complementarias(db_session, http, nuevo_sensor, valor, declarada,
                                                           correlacion, esperada, escala):
    r = _enviar(http, nuevo_sensor(), "TEMPERATURA_AMBIENTAL", valor, declarada, correlacion=correlacion)
    assert (r["tipo_alerta"], r["severidad"]) == ("ESTRES_TERMICO", esperada)
    evaluacion = _alerta(db_session, r["id_alerta"])["metadato_evento"]["evaluacion_rf57"]
    assert evaluacion["severidad_rf57"] == esperada
    assert ("escalada" in evaluacion) is escala

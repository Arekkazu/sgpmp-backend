# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-27 | destroyerban | INC-M03-119-G62 RF-56 E7: BOLA entre gateways y dispositivos revocados con el adaptador real |
"""INC-M03-119-G62 (RF-56 E7, TC-M03-124 y TC-M03-126): autenticación de eventos Edge.

Router real, DispositivoM09Adapter real y PostgreSQL real. Dos Gateway Edge en fincas distintas,
cada uno con su dispositivo y su sensor. Se verifica que el backend aplica la terna
(device_id, sensor_id, serial) y la revocación en M09 (dispositivo o sensor desactivados), sin
persistir el evento ni generar paquetes, y dejando el intento en la bitácora RF-63.

La credencial MQTT del Edge (alterada o revocada) la valida el broker, no el backend: ver
BROKER-MQTT-SGPMP, scripts/e2e_credenciales_mqtt.py. Aquí se cubre la credencial que sí recibe
el backend: el token de servicio del broker.
"""
from __future__ import annotations

import importlib
import pkgutil
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from src.shared.database import get_db_sistema
from src.shared.error_handlers import register_error_handlers
from src.telemetry.infrastructure.routers import evento_edge_router

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def modelos():
    for paquete in ("src.configuration.infrastructure.models", "src.biological_assets.infrastructure.models",
                    "src.telemetry.infrastructure.models", "src.identity_access.infrastructure.models"):
        mod = importlib.import_module(paquete)
        for item in pkgutil.iter_modules(mod.__path__, paquete + "."):
            importlib.import_module(item.name)


def _gateway_con_dispositivo(db, etiqueta: str) -> dict:
    tag = uuid.uuid4().hex[:10]
    nombre = f"Gateway {etiqueta} " + "".join(chr(97 + int(c, 16)) for c in tag)
    area = db.execute(text("""
        WITH finca AS (
          INSERT INTO modulo9.fincas(nombre,ubicacion,tamano_h,es_activo,fecha_creacion,fecha_actualizacion)
          VALUES (:nombre,'{}',10,true,now(),now()) RETURNING id_finca)
        INSERT INTO modulo9.infraestructuras(nombre,id_finca,superficie,es_activo,tipo)
        SELECT :nombre,id_finca,100,true,'Estanque' FROM finca RETURNING id_infraestructura
    """), {"nombre": nombre}).scalar_one()
    gateway = db.execute(text("""
        INSERT INTO modulo9.dispositivos_iot(serial,descripcion,es_activo,fecha_creacion,id_infraestructura,id_tipo_dispositivo)
        SELECT :serial,'G62 gateway',true,now(),:area,id_tipo_dispositivo
        FROM modulo9.tipos_dispositivo_iot WHERE nombre = 'GATEWAY_EDGE'
        RETURNING id_dispositivo_iot
    """), {"serial": f"GW-{tag}", "area": area}).scalar_one()
    device = db.execute(text("""
        INSERT INTO modulo9.dispositivos_iot(serial,descripcion,es_activo,fecha_creacion,id_infraestructura,
                                            id_tipo_dispositivo,id_dispositivo_gateway)
        VALUES (:serial,'G62 nodo',true,now(),:area,3,:gateway) RETURNING id_dispositivo_iot
    """), {"serial": f"ND-{tag}", "area": area, "gateway": gateway}).scalar_one()
    sensor = db.execute(text("""
        INSERT INTO modulo9.sensores(id_dispositivo_iot,es_activo,nombre)
        VALUES (:device,true,'Temperatura G62') RETURNING id_sensores
    """), {"device": device}).scalar_one()
    db.commit()
    return {"gateway": gateway, "device": device, "sensor": sensor, "serial": f"ND-{tag}"}


@pytest.fixture
def gateways(db_session):
    return _gateway_con_dispositivo(db_session, "A"), _gateway_con_dispositivo(db_session, "B")


@pytest.fixture
def intentos_token(monkeypatch):
    # El rechazo del token se registra con sesion_sistema() (DATABASE_URL): se captura aquí para
    # no escribir en otra base que no sea la de pruebas.
    capturados = []
    monkeypatch.setattr(evento_edge_router, "registrar_intento_no_autorizado",
                        lambda db, repo, **kw: capturados.append(kw))
    monkeypatch.setattr(evento_edge_router, "sesion_sistema", lambda: _SesionNula())
    return capturados


class _SesionNula:
    def close(self):
        pass


@pytest.fixture
def client(db_session, headers_broker):
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(evento_edge_router.router)
    app.dependency_overrides[get_db_sistema] = lambda: db_session
    with TestClient(app, raise_server_exceptions=False, headers=headers_broker) as test_client:
        yield test_client


def _payload(device_id, sensor_id, serial):
    ts = datetime.now(timezone.utc) - timedelta(seconds=30)
    return dict(device_id=device_id, sensor_id=sensor_id, serial=serial, clasificacion_rf55="DESVIACION_SIMPLE",
                severidad="MODERADO", origen="TIEMPO_REAL", estado_conectividad=True,
                timestamp_captura=ts.isoformat(), timestamp_procesamiento_edge=(ts + timedelta(milliseconds=200)).isoformat(),
                variables_involucradas=[{"tipo_variable": "TEMPERATURA_AMBIENTAL", "valor": "38.5", "unidad": "°C"}])


def _conteo(db, *dispositivos):
    eventos = db.execute(text("SELECT count(*) FROM modulo3.eventos_edge_computing WHERE id_dispositivo_iot = ANY(:d)"),
                         {"d": list(dispositivos)}).scalar_one()
    paquetes = db.execute(text("SELECT count(*) FROM modulo3.paquetes_inferencia WHERE id_dispositivo_iot = ANY(:d)"),
                          {"d": list(dispositivos)}).scalar_one()
    return eventos, paquetes


def _intentos_bitacora(db, serial):
    return db.execute(text(
        "SELECT accion_detallada->>'codigo_error' FROM modulo3.bitacora_auditoria_iot "
        "WHERE tipo_evento = 'INTENTO_NO_AUTORIZADO_EVENTO_EDGE' AND entidad_afectada_id = :s"), {"s": serial}).scalars().all()


def test_gateway_legitimo_es_aceptado(client, db_session, gateways):
    a, _ = gateways
    respuesta = client.post("/iot/eventos-edge", json=_payload(a["device"], a["sensor"], a["serial"]))
    assert respuesta.status_code == 201, respuesta.text
    assert _conteo(db_session, a["device"]) == (1, 1)


@pytest.mark.parametrize("caso", ["dispositivo_y_sensor_de_B", "sensor_de_B", "dispositivo_de_B"])
def test_bola_gateway_a_no_puede_enviar_por_el_gateway_b(client, db_session, gateways, caso):
    """TC-M03-126: autenticado como A (serial de A, que es lo que fija el broker desde el topic)."""
    a, b = gateways
    device, sensor = {"dispositivo_y_sensor_de_B": (b["device"], b["sensor"]),
                      "sensor_de_B": (a["device"], b["sensor"]),
                      "dispositivo_de_B": (b["device"], a["sensor"])}[caso]
    respuesta = client.post("/iot/eventos-edge", json=_payload(device, sensor, a["serial"]))
    assert respuesta.status_code == 401, respuesta.text
    assert respuesta.json()["error_code"] == "DISPOSITIVO_NO_AUTORIZADO"
    assert _conteo(db_session, a["device"], b["device"]) == (0, 0)
    assert _intentos_bitacora(db_session, a["serial"]) == ["DISPOSITIVO_NO_AUTORIZADO"]


@pytest.mark.parametrize("revocado", ["dispositivo", "sensor"])
def test_dispositivo_o_sensor_revocado_en_m09_es_rechazado(client, db_session, gateways, revocado):
    """TC-M03-124: revocación del lado del backend = desactivación en M09."""
    a, _ = gateways
    if revocado == "dispositivo":
        db_session.execute(text("UPDATE modulo9.dispositivos_iot SET es_activo = false WHERE id_dispositivo_iot = :d"),
                           {"d": a["device"]})
    else:
        db_session.execute(text("UPDATE modulo9.sensores SET es_activo = false WHERE id_sensores = :s"), {"s": a["sensor"]})
    db_session.commit()
    respuesta = client.post("/iot/eventos-edge", json=_payload(a["device"], a["sensor"], a["serial"]))
    assert respuesta.status_code == 401, respuesta.text
    assert respuesta.json()["error_code"] == "DISPOSITIVO_NO_AUTORIZADO"
    assert _conteo(db_session, a["device"]) == (0, 0)
    assert _intentos_bitacora(db_session, a["serial"]) == ["DISPOSITIVO_NO_AUTORIZADO"]


@pytest.mark.parametrize("cabecera", [None, "Bearer token-alterado", "Bearer "])
def test_token_del_broker_ausente_o_alterado_es_rechazado(db_session, gateways, headers_broker, intentos_token, cabecera):
    """TC-M03-124: la credencial que sí recibe el backend es el token de servicio del broker."""
    a, _ = gateways
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(evento_edge_router.router)
    app.dependency_overrides[get_db_sistema] = lambda: db_session
    headers = {"Authorization": cabecera} if cabecera is not None else {}
    with TestClient(app, raise_server_exceptions=False) as test_client:
        respuesta = test_client.post("/iot/eventos-edge", json=_payload(a["device"], a["sensor"], a["serial"]),
                                     headers=headers)
    assert respuesta.status_code == 401, respuesta.text
    assert _conteo(db_session, a["device"]) == (0, 0)
    assert len(intentos_token) == 1

# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-169-G77 RF-57 Fase 3/E6/CA-7: la alerta lleva el activo y su contexto |
# | 2026-10-28 | Arekkazu | INC-M03-169-G77 RF-57: el evento trae el pH que exige G70 para RIESGO_HIDRICO |
# | 2026-10-28 | Arekkazu | INC-M03-173-G85 RF-57 E9: el área de la prueba tiene umbrales RF-17 |
"""INC-M03-169-G77 (RF-57 Fase 3, E6, CA-7): POST /iot/alertas asocia el activo biológico del sensor.

Router real, adaptadores reales y PostgreSQL real. Reproduce el caso de QA: sensor asociado a un lote
(asociación ACTIVA) → la alerta queda con ese activo, su contexto y tiene_contexto_incompleto=false.
"""
from datetime import datetime, timedelta, timezone
import importlib
import pkgutil
import random
import string
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from src.shared.database import get_db_sistema
from src.shared.error_handlers import register_error_handlers
from src.telemetry.infrastructure.routers import alerta_router
from tests.integration.conftest import sembrar_umbrales_rf17

pytestmark = pytest.mark.integration

# G70 (#823): RIESGO_HIDRICO exige pH fuera de rango LEVE o TDS; el oxígeno solo es complementario.
_PH_RIESGO_HIDRICO = {"PH_AGUA": "8.6"}


def _sid():
    return uuid.uuid4().int % (10 ** 9)


def _letras(n=10):
    return "".join(random.choices(string.ascii_letters, k=n))


@pytest.fixture(autouse=True)
def modelos():
    for paquete in ("src.configuration.infrastructure.models", "src.biological_assets.infrastructure.models",
                    "src.telemetry.infrastructure.models", "src.identity_access.infrastructure.models"):
        modulo = importlib.import_module(paquete)
        for item in pkgutil.iter_modules(modulo.__path__, paquete + "."):
            importlib.import_module(item.name)


@pytest.fixture
def client(db_session, headers_broker):
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(alerta_router.router)
    app.dependency_overrides[get_db_sistema] = lambda: db_session
    with TestClient(app, raise_server_exceptions=False, headers=headers_broker) as c:
        yield c


@pytest.fixture
def escenario(db_session, crear_usuario_db):
    """Unidad productiva con un dispositivo y un sensor; activos y asociaciones a demanda."""
    usuario = crear_usuario_db()["id_usuario"]
    finca = db_session.execute(text("""INSERT INTO modulo9.fincas(nombre,ubicacion,tamano_h,fecha_actualizacion,
        fecha_creacion,es_activo) VALUES (:n,'{"lat": 2.93, "lon": -75.28}',10,now(),now(),TRUE) RETURNING id_finca"""),
        {"n": f"Finca Gsetentaysiete {_letras()}"}).scalar_one()
    area = db_session.execute(text("""INSERT INTO modulo9.infraestructuras(nombre,id_finca,superficie,es_activo,tipo)
        VALUES (:n,:f,100,TRUE,'Estanque') RETURNING id_infraestructura"""),
        {"n": f"Estanque {_letras()}", "f": finca}).scalar_one()
    serial = _letras(12)
    device = db_session.execute(text("""INSERT INTO modulo9.dispositivos_iot(serial,descripcion,es_activo,fecha_creacion,
        id_infraestructura,id_tipo_dispositivo) VALUES (:s,'G77',TRUE,now(),:a,3) RETURNING id_dispositivo_iot"""),
        {"s": serial, "a": area}).scalar_one()
    sembrar_umbrales_rf17(db_session, area, id_especie=2)
    sensor = db_session.execute(text("""INSERT INTO modulo9.sensores(id_dispositivo_iot,es_activo,nombre)
        VALUES (:d,TRUE,'Oxigeno G77') RETURNING id_sensores"""), {"d": device}).scalar_one()
    db_session.execute(text("""INSERT INTO modulo2.estados_activos_biologicos (id_estado_activo_biologico, nombre)
        VALUES (1, 'ACTIVO') ON CONFLICT (id_estado_activo_biologico) DO NOTHING"""))

    def activo(en_la_unidad=True):
        sid = _sid()
        # La auditoría de M02 (trg_auditar_activo_biologico) exige el usuario de la sesión.
        db_session.execute(text("SELECT set_config('app.usuario_id', :u, false)"), {"u": str(usuario)})
        db_session.execute(text("""INSERT INTO modulo2.activos_biologicos (id_activo_biologico, id_especie,
            identificador, id_infraestructura, tipo, fecha_inicio_ciclo, id_estado, descripcion, origen_financiero,
            costo_adquisicion, atributos_dinamicos, id_usuario, fecha_creacion, id_dispositivo_iot, soporte_documental,
            detalles_procedencia) VALUES (:id, 2, :ident, :area, 'INDIVIDUAL', current_date, 1, '', 'compra', 100,
            '{}', :u, now() - interval '2 hour', 0, 'doc', '')"""),
            {"id": sid, "ident": f"LOTE-G77-{sid}", "area": area, "u": usuario})
        if en_la_unidad:
            db_session.execute(text("""INSERT INTO modulo2.historial_infraestructura_activo(id_activo_biologico,
                id_infraestructura,fecha_inicio,id_usuario_registro) VALUES (:a,:i,now() - interval '2 hour',:u)"""),
                {"a": sid, "i": area, "u": usuario})
        db_session.commit()
        return sid

    def asociar(id_activo, tipo="directa", fecha_fin=None):
        db_session.execute(text("""INSERT INTO modulo2.asociaciones_activos_sensores(id_sensor,id_usuario,fecha_inicio,
            fecha_fin,id_activo_biologico,tipo,tipo_activo,id_infraestructura,estado_asociacion)
            VALUES (:s,:u,now() - interval '1 hour',:fin,:a,CAST(:t AS modulo2.enum_asociaciones_activos_sensores_tipo),
                    'INDIVIDUAL',:i,'ACTIVA')"""),
            {"s": sensor, "u": usuario, "fin": fecha_fin, "a": id_activo, "t": tipo, "i": area})
        db_session.commit()

    db_session.commit()
    return {"area": area, "finca": finca, "device": device, "sensor": sensor, "serial": serial,
            "activo": activo, "asociar": asociar}


def _alerta(client, db, e):
    id_lectura = db.execute(text("""INSERT INTO modulo3.telemetrias(id_sensor,id_variable,id_dispositivo_iot,valor_crudo,
        timestamp_captura,timestamp_procesamiento,origen,estado_calidad,metadatos,categoria_variable,unidad_medida)
        VALUES (:s,3,:d,4.0,now() - interval '1 minute',now(),'TIEMPO_REAL','LECTURA_VALIDA','{}','HIDRICA','mg/L')
        RETURNING id_telemetria"""), {"s": e["sensor"], "d": e["device"]}).scalar_one()
    db.commit()
    r = client.post("/iot/alertas", json={
        "device_id": e["device"], "sensor_id": e["sensor"], "serial": e["serial"], "tipo_variable": "OXIGENO_DISUELTO",
        "valor": "4.0", "unidad": "mg/L", "timestamp_evento": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        "estado_dato": "LECTURA_VALIDA", "severidad_edge": "LEVE", "origen_evento": "EDGE", "id_telemetria": id_lectura,
        "correlacion_variables": _PH_RIESGO_HIDRICO})
    assert r.status_code == 201, r.text
    return db.execute(text("SELECT to_jsonb(a) FROM modulo3.alertas a WHERE id_alerta=:id"),
                      {"id": r.json()["id_alerta"]}).scalar_one()


def test_sensor_asociado_al_lote_da_contexto_completo(client, db_session, escenario):
    """Caso de QA: asociación ACTIVA del sensor con el lote (y otros activos en la unidad)."""
    lote = escenario["activo"]()
    escenario["activo"]()  # otro activo en la misma unidad: la asociación explícita decide
    escenario["asociar"](lote)
    a = _alerta(client, db_session, escenario)
    assert a["tiene_contexto_incompleto"] is False and a["id_activo_biologico"] == lote
    c = a["contexto_activo_biologico"]
    assert c["id_activo_biologico"] == lote and c["identificador"] == f"LOTE-G77-{lote}"
    assert c["id_especie"] == 2 and c["especie"]
    assert c["unidad_productiva"]["id_infraestructura"] == escenario["area"]
    assert c["ubicacion"]["id_finca"] == escenario["finca"] and c["ubicacion"]["geografica"] == {"lat": 2.93, "lon": -75.28}
    assert c["fuente_vinculacion"] == "ASOCIACION_SENSOR"


def test_asociacion_poblacional_tambien_cuenta(client, db_session, escenario):
    lote = escenario["activo"]()
    escenario["asociar"](lote, tipo="poblacional")
    assert _alerta(client, db_session, escenario)["id_activo_biologico"] == lote


def test_asociacion_ambiental_de_un_solo_activo(client, db_session, escenario):
    activo = escenario["activo"]()
    escenario["asociar"](activo, tipo="ambiental")
    a = _alerta(client, db_session, escenario)
    assert a["id_activo_biologico"] == activo
    assert a["contexto_activo_biologico"]["fuente_vinculacion"] == "ASOCIACION_AMBIENTAL"


def test_varias_asociaciones_ambientales_es_contexto_incompleto(client, db_session, escenario):
    for _ in range(2):
        escenario["asociar"](escenario["activo"](), tipo="ambiental")
    a = _alerta(client, db_session, escenario)
    assert a["tiene_contexto_incompleto"] is True and a["id_activo_biologico"] is None
    assert a["metadato_evento"]["contexto_incompleto"] == {"motivo": "VARIOS_ACTIVOS_CANDIDATOS",
                                                           "fuente": "ASOCIACION_AMBIENTAL"}
    assert a["id_infraestructura"] == escenario["area"]  # E6: queda al menos con la unidad


def test_sin_asociacion_y_un_activo_en_la_unidad(client, db_session, escenario):
    activo = escenario["activo"]()
    a = _alerta(client, db_session, escenario)
    assert a["id_activo_biologico"] == activo
    assert a["contexto_activo_biologico"]["fuente_vinculacion"] == "UNIDAD_PRODUCTIVA"


def test_sin_activos_es_contexto_incompleto_ca7(client, db_session, escenario):
    a = _alerta(client, db_session, escenario)
    assert (a["tiene_contexto_incompleto"], a["id_activo_biologico"], a["contexto_activo_biologico"]) == (True, None, None)
    assert a["metadato_evento"]["contexto_incompleto"]["motivo"] == "SIN_ACTIVO_ASOCIADO"


def test_asociacion_vencida_no_cuenta(client, db_session, escenario):
    activo = escenario["activo"](en_la_unidad=False)
    escenario["asociar"](activo, fecha_fin=datetime.now(timezone.utc) - timedelta(minutes=30))
    assert _alerta(client, db_session, escenario)["id_activo_biologico"] is None


def test_vinculacion_rf61_de_la_lectura_prevalece(client, db_session, escenario):
    asociado, vinculado = escenario["activo"](), escenario["activo"]()
    escenario["asociar"](asociado)
    id_lectura = db_session.execute(text("""INSERT INTO modulo3.telemetrias(id_sensor,id_variable,id_dispositivo_iot,
        valor_crudo,timestamp_captura,timestamp_procesamiento,origen,estado_calidad,metadatos,categoria_variable,unidad_medida)
        VALUES (:s,3,:d,4.0,now() - interval '1 minute',now(),'TIEMPO_REAL','LECTURA_VALIDA','{}','HIDRICA','mg/L')
        RETURNING id_telemetria"""), {"s": escenario["sensor"], "d": escenario["device"]}).scalar_one()
    db_session.execute(text("""INSERT INTO modulo3.vinculaciones_lecturas(id_telemetria,modelo_manejo,id_activo_biologico,
        id_infraestructura,fecha_inicio_vinculacion,mecanismo_vinculacion,estado_vinculacion,fecha_creacion)
        VALUES (:l,'INDIVIDUAL',:a,:i,now(),'AUTOMATICA','CONFIRMADA',now())"""),
        {"l": id_lectura, "a": vinculado, "i": escenario["area"]})
    db_session.commit()
    r = client.post("/iot/alertas", json={
        "device_id": escenario["device"], "sensor_id": escenario["sensor"], "serial": escenario["serial"],
        "tipo_variable": "OXIGENO_DISUELTO", "valor": "4.0", "unidad": "mg/L",
        "timestamp_evento": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        "estado_dato": "LECTURA_VALIDA", "severidad_edge": "LEVE", "origen_evento": "EDGE", "id_telemetria": id_lectura,
        "correlacion_variables": _PH_RIESGO_HIDRICO})
    assert r.status_code == 201, r.text
    a = db_session.execute(text("SELECT id_activo_biologico, contexto_activo_biologico->>'fuente_vinculacion' "
                                "FROM modulo3.alertas WHERE id_alerta=:id"), {"id": r.json()["id_alerta"]}).one()
    assert tuple(a) == (vinculado, "VINCULACION_RF61")

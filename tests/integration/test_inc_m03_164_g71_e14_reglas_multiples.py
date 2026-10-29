# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-164-G71 RF-57 E14: compuesta con dos sensores del área y consolidación por HTTP |
# | 2026-10-28 | Arekkazu | INC-M03-173-G85 RF-57 E9: el área de la prueba tiene umbrales RF-17 |
"""INC-M03-164-G71 (RF-57 E14, TC-M03-G71): varias reglas simples activas a la vez.

Router real, adaptadores reales y PostgreSQL real. Un dispositivo con dos sensores (temperatura y
humedad) en la misma área, como el dispositivo 339 de QA (sensores 525 y 526).
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.integration.conftest import sembrar_umbrales_rf17
from tests.integration.test_inc_m03_162_g68_severidad_alertas_rf57 import http, modelos  # noqa: F401

pytestmark = pytest.mark.integration


@pytest.fixture
def area(db_session):
    """Dispositivo con un sensor de temperatura y otro de humedad en la misma área."""
    def crear():
        tag = uuid4().hex[:12]
        nombre = "Gsetentayuno " + "".join(chr(97 + int(c, 16)) for c in tag)
        id_area = db_session.execute(text("""
            WITH finca AS (
                INSERT INTO modulo9.fincas(nombre,ubicacion,tamano_h,es_activo,fecha_creacion,fecha_actualizacion)
                VALUES (:nombre,'{}',10,true,now(),now()) RETURNING id_finca)
            INSERT INTO modulo9.infraestructuras(nombre,id_finca,superficie,es_activo,tipo)
            SELECT :nombre,id_finca,100,true,'Estanque' FROM finca RETURNING id_infraestructura
        """), {"nombre": nombre}).scalar_one()
        device = db_session.execute(text("""
            INSERT INTO modulo9.dispositivos_iot(serial,descripcion,es_activo,fecha_creacion,id_infraestructura,id_tipo_dispositivo)
            VALUES (:serial,'G71',true,now(),:area,3) RETURNING id_dispositivo_iot
        """), {"serial": tag, "area": id_area}).scalar_one()
        sembrar_umbrales_rf17(db_session, id_area)
        sensores = {v: db_session.execute(text("""
            INSERT INTO modulo9.sensores(id_dispositivo_iot,es_activo,nombre)
            VALUES (:device,true,:nombre) RETURNING id_sensores
        """), {"device": device, "nombre": f"Sensor {v}"}).scalar_one() for v in ("TEMPERATURA_AMBIENTAL", "HUMEDAD_RELATIVA")}
        db_session.commit()
        return {"area": id_area, "device": device, "serial": tag, "sensores": sensores}
    return crear


_UNIDAD = {"TEMPERATURA_AMBIENTAL": "°C", "HUMEDAD_RELATIVA": "%"}


def _lectura(db, hw, variable, valor, hace_min=1):
    id_variable = db.execute(text("SELECT id_variable_ambiental FROM modulo9.variables_ambientales "
                                  "WHERE codigo_telemetria=:c"), {"c": variable}).scalar_one()
    id_lectura = db.execute(text("""
        INSERT INTO modulo3.telemetrias(id_sensor,id_variable,id_dispositivo_iot,valor_crudo,
          timestamp_captura,timestamp_procesamiento,origen,estado_calidad,metadatos,categoria_variable,unidad_medida)
        VALUES (:s,:var,:d,:v,:captura,now(),'TIEMPO_REAL','LECTURA_VALIDA','{}','AMBIENTAL',:u) RETURNING id_telemetria
    """), {"s": hw["sensores"][variable], "var": id_variable, "d": hw["device"], "v": valor, "u": _UNIDAD[variable],
           "captura": datetime.now(timezone.utc) - timedelta(minutes=hace_min)}).scalar_one()
    db.commit()
    return id_lectura


def _evento(http, hw, variable, valor, severidad="LEVE", reglas=None):
    client, _, broker, db = http
    cuerpo = {"device_id": hw["device"], "sensor_id": hw["sensores"][variable], "serial": hw["serial"],
              "tipo_variable": variable, "valor": str(valor), "unidad": _UNIDAD[variable],
              "timestamp_evento": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
              "estado_dato": "LECTURA_VALIDA", "severidad_edge": severidad, "origen_evento": "EDGE",
              "id_telemetria": _lectura(db, hw, variable, valor), "reglas_activadas": reglas or []}
    return client.post("/iot/alertas", headers=broker, json=cuerpo)


def _alertas(db, hw):
    return db.execute(text("SELECT to_jsonb(a) FROM modulo3.alertas a WHERE id_infraestructura=:a ORDER BY id_alerta"),
                      {"a": hw["area"]}).scalars().all()


def _nombres(alerta):
    return [r["nombre"] for r in alerta["reglas_activas"] if isinstance(r, dict)]


def test_temperatura_y_humedad_en_la_ventana_generan_una_sola_compuesta(db_session, http, con_humedad_previa):
    """Escenario 1 de QA: 31 °C (LEVE) y 75 % (LEVE) en sensores distintos → una ESTRES_TERMICO.

    Las dos lecturas ya están ingeridas (RF-53) cuando llegan los eventos de alerta.
    """
    hw = con_humedad_previa
    primero = _evento(http, hw, "TEMPERATURA_AMBIENTAL", "31.0", reglas=["TEMPERATURA_LEVE"])
    assert primero.status_code == 201, primero.text
    assert primero.json()["tipo_alerta"] == "ESTRES_TERMICO"
    segundo = _evento(http, hw, "HUMEDAD_RELATIVA", "75", reglas=["HUMEDAD_LEVE"])
    assert segundo.status_code == 201, segundo.text
    assert segundo.json()["es_duplicado"] and segundo.json()["alerta_existente_id"] == primero.json()["id_alerta"]

    alertas = _alertas(db_session, hw)
    assert len(alertas) == 1
    alerta = alertas[0]
    assert alerta["tipo_alerta"] == "ESTRES_TERMICO" and alerta["severidad"] == "MODERADO"  # THI 83.70
    assert alerta["frecuencia_evento"] == 2
    nombres = _nombres(alerta)
    assert {"TEMPERATURA_AMBIENTAL_LEVE", "HUMEDAD_RELATIVA_LEVE", "ESTRES_TERMICO"} <= set(nombres)
    assert "TEMPERATURA_LEVE" in alerta["reglas_activas"] and "HUMEDAD_LEVE" in alerta["reglas_activas"]
    simples = [(r["id"], r["id_sensor"]) for r in alerta["reglas_activas"]
               if isinstance(r, dict) and r["tipo"] == "REGLA_SIMPLE_RF57"]
    assert len(simples) == len(set(simples))  # sin reglas repetidas al consolidar
    assert alerta["metadato_evento"]["e14"]["evento_correlacionado"] is True
    assert db_session.execute(text(
        "SELECT count(*) FROM modulo3.bitacora_auditoria_iot WHERE tipo_evento='REGLAS_MULTIPLES_CORRELACIONADAS' "
        "AND entidad_afectada_id=:id"), {"id": str(alerta["id_alerta"])}).scalar_one() == 2


@pytest.fixture
def con_humedad_previa(db_session, area):
    hw = area()
    _lectura(db_session, hw, "HUMEDAD_RELATIVA", "75")
    return hw


def test_la_compuesta_registra_la_lectura_companera(db_session, http, con_humedad_previa):
    hw = con_humedad_previa
    r = _evento(http, hw, "TEMPERATURA_AMBIENTAL", "31.0")
    assert r.status_code == 201, r.text
    alerta, = _alertas(db_session, hw)
    companera, = alerta["metadato_evento"]["e14"]["lecturas_correlacionadas"]
    assert companera["tipo_variable"] == "HUMEDAD_RELATIVA" and companera["id_sensor"] == hw["sensores"]["HUMEDAD_RELATIVA"]
    assert alerta["metadato_evento"]["evaluacion_rf57"]["thi"] == "83.70"


def test_lectura_companera_fuera_de_la_ventana_no_cuenta(db_session, http, area):
    hw = area()
    _lectura(db_session, hw, "HUMEDAD_RELATIVA", "75", hace_min=15)  # ventana de ESTRES_TERMICO: 10 min
    r = _evento(http, hw, "TEMPERATURA_AMBIENTAL", "31.0")
    assert r.status_code == 422 and r.json()["error_code"] == "REGLA_COMPUESTA_NO_ACTIVADA", r.text


def test_lectura_companera_de_otra_area_no_cuenta(db_session, http, area):
    otra, hw = area(), area()
    _lectura(db_session, otra, "HUMEDAD_RELATIVA", "75")
    r = _evento(http, hw, "TEMPERATURA_AMBIENTAL", "31.0")
    assert r.status_code == 422 and r.json()["error_code"] == "REGLA_COMPUESTA_NO_ACTIVADA", r.text


def test_escenario_sin_compuesta_aplicable_queda_bloqueado(db_session, http, area):
    """Escenario 2 de QA: HR 45 % y 19 °C (THI bajo 72). Sin tipo para alertas simples (G70) → 422."""
    hw = area()
    humedad = _evento(http, hw, "HUMEDAD_RELATIVA", "45")
    temperatura = _evento(http, hw, "TEMPERATURA_AMBIENTAL", "19.0")
    assert [humedad.status_code, temperatura.status_code] == [422, 422]
    assert {humedad.json()["error_code"], temperatura.json()["error_code"]} == {"REGLA_COMPUESTA_NO_ACTIVADA"}
    assert _alertas(db_session, hw) == []

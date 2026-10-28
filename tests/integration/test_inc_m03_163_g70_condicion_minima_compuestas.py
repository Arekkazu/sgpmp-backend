# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-163-G70 RF-57: condición mínima de las compuestas por HTTP (G70, G71, G72) |
# | 2026-10-28 | destroyerban | INC-M03-164-G71 RF-57 E14: la lectura de prueba usa la variable del evento |
"""INC-M03-163-G70 (RF-57 Fase 5, TC-M03-G70/G71/G72): sin condición mínima no hay alerta compuesta.

Router real, adaptadores de M09 y PostgreSQL real. Reutiliza las fixtures de G68.
"""
import pytest
from sqlalchemy import text

from tests.integration.test_inc_m03_162_g68_severidad_alertas_rf57 import (  # noqa: F401
    _UNIDAD, _alerta, _lectura, http, modelos, nuevo_sensor,
)

pytestmark = pytest.mark.integration

_UNIDAD.update({"PH_AGUA": "pH", "TDS": "µS/cm"})


def _post(http, hw, variable, valor, severidad, correlacion=None, reglas=None):
    from datetime import datetime, timedelta, timezone
    client, _, broker, db = http
    cuerpo = {"device_id": hw["device"], "sensor_id": hw["sensor"], "serial": hw["serial"],
              "tipo_variable": variable, "valor": str(valor), "unidad": _UNIDAD[variable],
              "timestamp_evento": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
              "estado_dato": "LECTURA_VALIDA", "severidad_edge": severidad, "origen_evento": "EDGE",
              "id_telemetria": _lectura(db, hw, valor, "LECTURA_VALIDA", variable)}
    if correlacion is not None:
        cuerpo["correlacion_variables"] = correlacion
    if reglas is not None:
        cuerpo["reglas_activadas"] = reglas
    return client.post("/iot/alertas", headers=broker, json=cuerpo)


def _rechazo(db, respuesta, hw, codigo):
    assert respuesta.status_code == 422, respuesta.text
    assert respuesta.json()["error_code"] == codigo
    assert db.execute(text("SELECT count(*) FROM modulo3.alertas WHERE id_sensor=:s"), {"s": hw["sensor"]}).scalar_one() == 0
    assert db.execute(text(
        "SELECT count(*) FROM modulo3.bitacora_auditoria_iot WHERE tipo_evento=:t AND accion_detallada->>'id_sensor'=:s"),
        {"t": codigo, "s": str(hw["sensor"])}).scalar_one() == 1


# ---------------------------------------------------------------- TC-M03-G70: RIESGO_HIDRICO

def test_oxigeno_aislado_no_activa_riesgo_hidrico(db_session, http, nuevo_sensor):
    hw = nuevo_sensor()
    _rechazo(db_session, _post(http, hw, "OXIGENO_DISUELTO", "4.0", "LEVE"), hw, "REGLA_COMPUESTA_NO_ACTIVADA")


@pytest.mark.parametrize("correlacion", [{"PH_AGUA": 6.4}, {"TDS": 1200}])
def test_oxigeno_con_ph_o_tds_en_leve_activa_riesgo_hidrico(http, nuevo_sensor, correlacion):
    r = _post(http, nuevo_sensor(), "OXIGENO_DISUELTO", "4.0", "LEVE", correlacion=correlacion)
    assert r.status_code == 201, r.text
    assert (r.json()["tipo_alerta"], r.json()["severidad"]) == ("RIESGO_HIDRICO", "LEVE")


@pytest.mark.parametrize("variable,valor", [("PH_AGUA", "6.4"), ("TDS", "1200")])
def test_ph_o_tds_cumplen_la_condicion_por_si_mismos(http, nuevo_sensor, variable, valor):
    r = _post(http, nuevo_sensor(), variable, valor, "LEVE")
    assert r.status_code == 201 and r.json()["tipo_alerta"] == "RIESGO_HIDRICO", r.text


# ---------------------------------------------------------------- TC-M03-G71: compuesta declarada sin condición

def test_temperatura_que_declara_estres_termico_sin_humedad_es_incoherente(db_session, http, nuevo_sensor):
    hw = nuevo_sensor()
    r = _post(http, hw, "TEMPERATURA_AMBIENTAL", "31.0", "LEVE", reglas=["ESTRES_TERMICO"])
    _rechazo(db_session, r, hw, "EVENTO_INCOHERENTE_REGLA_COMPUESTA")


def test_declaracion_como_objeto_tambien_se_valida(db_session, http, nuevo_sensor):
    hw = nuevo_sensor()
    r = _post(http, hw, "TEMPERATURA_AMBIENTAL", "31.0", "LEVE", reglas=[{"id": 9, "nombre": "ESTRES_TERMICO"}])
    _rechazo(db_session, r, hw, "EVENTO_INCOHERENTE_REGLA_COMPUESTA")


def test_temperatura_con_humedad_declara_bien_la_compuesta(db_session, http, nuevo_sensor):
    r = _post(http, nuevo_sensor(), "TEMPERATURA_AMBIENTAL", "31.0", "LEVE",
              correlacion={"HUMEDAD_RELATIVA": 75}, reglas=["ESTRES_TERMICO"])
    assert r.status_code == 201, r.text
    assert (r.json()["tipo_alerta"], r.json()["severidad"]) == ("ESTRES_TERMICO", "MODERADO")  # THI 83.70
    assert _alerta(db_session, r.json()["id_alerta"])["metadato_evento"]["evaluacion_rf57"]["thi"] == "83.70"


@pytest.mark.parametrize("variable,valor", [("TEMPERATURA_AMBIENTAL", "31.0"), ("HUMEDAD_RELATIVA", "75")])
def test_variable_de_estres_termico_sin_la_otra_no_activa_la_compuesta(db_session, http, nuevo_sensor, variable, valor):
    hw = nuevo_sensor()
    _rechazo(db_session, _post(http, hw, variable, valor, "LEVE"), hw, "REGLA_COMPUESTA_NO_ACTIVADA")


def test_compuesta_declarada_distinta_de_la_variable_se_valida(db_session, http, nuevo_sensor):
    hw = nuevo_sensor()
    r = _post(http, hw, "TEMPERATURA_AMBIENTAL", "31.0", "LEVE", correlacion={"THI": 80}, reglas=["RIESGO_HIDRICO"])
    _rechazo(db_session, r, hw, "EVENTO_INCOHERENTE_REGLA_COMPUESTA")


# ---------------------------------------------------------------- TC-M03-G72: THI por debajo de 72

def test_thi_normal_con_temperatura_normal_no_genera_alerta(db_session, http, nuevo_sensor):
    """24.4 °C y 60 % → THI 71.98 (NRC): banda NORMAL, sin alerta."""
    hw = nuevo_sensor()
    r = _post(http, hw, "TEMPERATURA_AMBIENTAL", "24.4", "LEVE", correlacion={"HUMEDAD_RELATIVA": 60})
    assert r.status_code == 201 and r.json()["id_alerta"] is None, r.text
    assert db_session.execute(text("SELECT count(*) FROM modulo3.alertas WHERE id_sensor=:s"),
                              {"s": hw["sensor"]}).scalar_one() == 0


@pytest.mark.parametrize("correlacion", [{"THI": 71.98}, {"HUMEDAD_RELATIVA": 2}])  # 31 °C y 2 % → THI 71.74
def test_thi_bajo_72_no_activa_estres_termico_aunque_la_temperatura_este_en_leve(db_session, http, nuevo_sensor,
                                                                                 correlacion):
    hw = nuevo_sensor()
    r = _post(http, hw, "TEMPERATURA_AMBIENTAL", "31.0", "LEVE", correlacion=correlacion)
    _rechazo(db_session, r, hw, "REGLA_COMPUESTA_NO_ACTIVADA")

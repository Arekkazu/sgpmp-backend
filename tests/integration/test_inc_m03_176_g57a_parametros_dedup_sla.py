# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-176-G57A RF-57: deduplicación y SLA configurados por API y aplicados (PostgreSQL real) |
"""INC-M03-176-G57A (RF-57, TC-M03-G57A N37 y G57B N44): ventana de deduplicación y SLA por API.

El administrador los cambia en PATCH /configuracion/parametros-alertas y POST /iot/alertas los aplica.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from tests.integration.test_inc_m03_168_g76_umbral_confianza_edge_ia import _sensor, http, modelos  # noqa: F401

pytestmark = pytest.mark.integration

_PARAMETROS = ("rf57_ventana_deduplicacion_min", "rf57_sla_critico_min", "rf57_sla_moderado_min", "rf57_sla_leve_min")


@pytest.fixture(autouse=True)
def sin_parametros(db_session):
    db_session.execute(text("DELETE FROM modulo4.parametros_mlops WHERE nombre_parametro = ANY(:n)"),
                       {"n": list(_PARAMETROS)})
    db_session.commit()


def _patch(http, **parametros):
    client, usuarios, _ = http
    return client.patch("/configuracion/parametros-alertas", headers=usuarios["admin"], json={"parametros": parametros})


def _evento(http, db, hw, severidad="CRITICO"):
    client, _, broker = http
    id_lectura = db.execute(text("""INSERT INTO modulo3.telemetrias(id_sensor,id_variable,id_dispositivo_iot,valor_crudo,
        timestamp_captura,timestamp_procesamiento,origen,estado_calidad,metadatos,categoria_variable,unidad_medida)
        VALUES (:s,9,:d,31,clock_timestamp() - interval '1 minute',now(),'TIEMPO_REAL','LECTURA_VALIDA','{}','AMBIENTAL','°C')
        RETURNING id_telemetria"""), {"s": hw["sensor"], "d": hw["device"]}).scalar_one()
    db.commit()
    return client.post("/iot/alertas", headers=broker, json={
        "device_id": hw["device"], "sensor_id": hw["sensor"], "serial": hw["serial"], "tipo_variable": "TEMPERATURA_AMBIENTAL",
        "valor": "31", "unidad": "°C", "timestamp_evento": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        "estado_dato": "LECTURA_VALIDA", "severidad_edge": severidad, "origen_evento": "EDGE", "id_telemetria": id_lectura})


def _alerta_previa(db, hw, hace_min):
    """Alerta ACTIVA de la misma condición generada hace ``hace_min`` minutos (INSERT: el trigger solo
    impide cambiar fecha_generacion después)."""
    db.execute(text("""INSERT INTO modulo3.alertas(tipo_alerta,severidad,estado_alerta,origen_evento,tipo_variable,
        fecha_evento,fecha_generacion,id_sensor,id_dispositivo_ioit) VALUES ('ESTRES_TERMICO','LEVE','ACTIVA','EDGE',
        'TEMPERATURA_AMBIENTAL',now(),now() - make_interval(mins => :m),:s,:d)"""),
               {"m": hace_min, "s": hw["sensor"], "d": hw["device"]})
    db.commit()


def test_n37_consulta_y_cambio_de_la_ventana_de_deduplicacion(http, db_session):
    client, usuarios, _ = http
    antes = {p["nombre"]: p for p in client.get("/configuracion/parametros-alertas", headers=usuarios["admin"]).json()}
    assert (antes["rf57_ventana_deduplicacion_min"]["fuente"], antes["rf57_ventana_deduplicacion_min"]["valor"]) == (
        "VALOR_BASE", 30)
    hw = _sensor(db_session)
    _alerta_previa(db_session, hw, hace_min=10)
    assert _evento(http, db_session, hw).json()["es_duplicado"] is True  # 10 min < 30: se consolida

    assert _patch(http, rf57_ventana_deduplicacion_min=5).status_code == 200
    hw2 = _sensor(db_session)
    _alerta_previa(db_session, hw2, hace_min=10)
    assert _evento(http, db_session, hw2).json()["es_duplicado"] is False  # 10 min > 5: alerta nueva


def test_n44_plazos_sla_configurados_se_aplican_al_vencimiento(http, db_session):
    assert _patch(http, rf57_sla_critico_min=2, rf57_sla_moderado_min=15, rf57_sla_leve_min=45).status_code == 200
    for severidad, minutos in (("CRITICO", 2), ("MODERADO", 15), ("LEVE", 45)):
        r = _evento(http, db_session, _sensor(db_session), severidad)
        assert r.status_code == 201, r.text
        generacion, vencimiento = db_session.execute(text(
            "SELECT fecha_generacion, fecha_vencimiento FROM modulo3.alertas WHERE id_alerta=:id"),
            {"id": r.json()["id_alerta"]}).one()
        assert vencimiento - generacion == timedelta(minutes=minutos), severidad


def test_sin_configurar_el_vencimiento_usa_los_plazos_del_rf(http, db_session):
    r = _evento(http, db_session, _sensor(db_session), "CRITICO")
    generacion, vencimiento = db_session.execute(text(
        "SELECT fecha_generacion, fecha_vencimiento FROM modulo3.alertas WHERE id_alerta=:id"),
        {"id": r.json()["id_alerta"]}).one()
    assert vencimiento - generacion == timedelta(minutes=5)


@pytest.mark.parametrize("parametros", [{"rf57_sla_critico_min": 0}, {"rf57_ventana_deduplicacion_min": 2.5},
                                        {"rf57_sla_leve_min": "x"}])
def test_valores_invalidos_son_400(http, parametros):
    assert _patch(http, **parametros).status_code == 400

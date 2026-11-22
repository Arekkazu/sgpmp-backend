# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-10-31 | Claude | INC-M03-241-G74 RF-57: PREDICCION_PATOLOGIA se deduplica por tipo + activo biológico |
"""INC-M03-241-G74 (#882, TC-M03-G74 N11): dos predicciones de IA de sensores distintos del mismo
activo, dentro de la ventana de deduplicación, deben consolidarse en una sola alerta.

Router real y PostgreSQL real; escenario de G77 (sensor asociado a un activo).
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from tests.integration.test_inc_m03_169_g77_contexto_activo_alerta import client, escenario, modelos  # noqa: F401

pytestmark = pytest.mark.integration


def _segundo_sensor(db, e, activo):
    sensor = db.execute(text("""INSERT INTO modulo9.sensores(id_dispositivo_iot,es_activo,nombre)
        VALUES (:d,TRUE,'Temperatura G74') RETURNING id_sensores"""), {"d": e["device"]}).scalar_one()
    usuario = db.execute(text("SELECT id_usuario FROM modulo1.usuarios ORDER BY id_usuario DESC LIMIT 1")).scalar_one()
    db.execute(text("""INSERT INTO modulo2.asociaciones_activos_sensores(id_sensor,id_usuario,fecha_inicio,
        id_activo_biologico,tipo,tipo_activo,id_infraestructura,estado_asociacion)
        VALUES (:s,:u,now() - interval '1 hour',:a,'directa','INDIVIDUAL',:i,'ACTIVA')"""),
        {"s": sensor, "u": usuario, "a": activo, "i": e["area"]})
    db.commit()
    return sensor


def _prediccion(client, db, e, sensor):
    lectura = db.execute(text("""INSERT INTO modulo3.telemetrias(id_sensor,id_variable,id_dispositivo_iot,valor_crudo,
        timestamp_captura,timestamp_procesamiento,origen,estado_calidad,metadatos,categoria_variable,unidad_medida)
        VALUES (:s,9,:d,31,now() - interval '1 minute',now(),'TIEMPO_REAL','LECTURA_VALIDA','{}','AMBIENTAL','°C')
        RETURNING id_telemetria"""), {"s": sensor, "d": e["device"]}).scalar_one()
    db.commit()
    return client.post("/iot/alertas", json={
        "device_id": e["device"], "sensor_id": sensor, "serial": e["serial"],
        "tipo_variable": "TEMPERATURA_AMBIENTAL", "valor": "31", "unidad": "°C",
        "timestamp_evento": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        "estado_dato": "LECTURA_VALIDA", "severidad_edge": "LEVE", "origen_evento": "IA",
        "tipo_alerta_ia": "PREDICCION_PATOLOGIA", "severidad_ia": "MODERADO", "probabilidad_ia": 0.85,
        "id_telemetria": lectura})


def _abiertas(db, activo):
    return db.execute(text("""SELECT id_alerta, frecuencia_evento FROM modulo3.alertas
        WHERE id_activo_biologico=:a AND tipo_alerta='PREDICCION_PATOLOGIA' AND estado_alerta='ACTIVA'"""),
        {"a": activo}).all()


def test_dos_sensores_del_mismo_activo_consolidan_una_prediccion(client, db_session, escenario):
    activo = escenario["activo"]()
    escenario["asociar"](activo)
    otro_sensor = _segundo_sensor(db_session, escenario, activo)

    primera = _prediccion(client, db_session, escenario, escenario["sensor"])
    segunda = _prediccion(client, db_session, escenario, otro_sensor)

    assert primera.status_code == 201 and segunda.status_code == 201, (primera.text, segunda.text)
    assert primera.json()["es_duplicado"] is False
    assert segunda.json()["es_duplicado"] is True
    assert segunda.json()["alerta_existente_id"] == primera.json()["id_alerta"]
    abiertas = _abiertas(db_session, activo)
    assert len(abiertas) == 1 and abiertas[0].frecuencia_evento == 2


def test_activos_distintos_no_se_consolidan(client, db_session, escenario):
    activo = escenario["activo"]()
    escenario["asociar"](activo)
    otro_activo = escenario["activo"]()
    otro_sensor = _segundo_sensor(db_session, escenario, otro_activo)

    primera = _prediccion(client, db_session, escenario, escenario["sensor"])
    segunda = _prediccion(client, db_session, escenario, otro_sensor)

    assert primera.json()["es_duplicado"] is False and segunda.json()["es_duplicado"] is False, segunda.text
    assert primera.json()["id_alerta"] != segunda.json()["id_alerta"]

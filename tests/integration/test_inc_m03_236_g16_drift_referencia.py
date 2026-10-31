# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-10-31 | Claude | INC-M03-236-G16 RF-62: posible_drift contra el valor de referencia de RF-24 |
"""INC-M03-236-G16 (#876, TC-M03-068): con calibración neutra (ganancia 1, offset 0) la
deriva calculada era siempre 0 %, porque comparaba las lecturas crudas con esas mismas
lecturas calibradas. Ahora se compara contra el valor de referencia de la calibración.
"""
from datetime import timedelta

import pytest
from sqlalchemy import text

from tests.integration.test_inc_m03_104_g165_motor_calidad import equipo_g165, insertar_serie, rutas_g165  # noqa: F401

pytestmark = pytest.mark.integration


def _calibrar(db, e, referencia):
    usuario = db.execute(text('SELECT id_usuario FROM modulo1.usuarios ORDER BY id_usuario LIMIT 1')).scalar_one()
    db.execute(text('''INSERT INTO modulo9.calibraciones
        (id_sensor,id_dispositivo_iot,fecha_calibracion,valor_referencia,id_usuario,ganancia,offset_calibracion)
        VALUES (:s,:d,now() - interval '30 days',:r,:u,1,0)'''),
        {'s': e['sensor'], 'd': e['dispositivo'], 'r': referencia, 'u': usuario})
    db.commit()


@pytest.mark.parametrize('valor,esperado', [(28.0, True), (25.5, False)])
def test_deriva_contra_la_referencia_con_calibracion_neutra(client, db_session, equipo_g165, valor, esperado):
    e = equipo_g165
    _calibrar(db_session, e, 25)
    lectura = insertar_serie(db_session, e, [valor] * 20, valor)   # +3 °C = 12 % sobre 25 (> 5 %)

    r = client.post(f'/iot/calidad/{lectura}/evaluar', headers=e['headers'])

    assert r.status_code == 201, r.text
    flags = r.json()['flags_detectados']
    assert bool(flags.get('posible_drift', {}).get('activo')) is esperado
    if esperado:
        drift = flags['posible_drift']
        assert drift['valor_calibrado_esperado'] == 25
        assert drift['media_ultimas_N'] == pytest.approx(28)
        assert drift['magnitud_drift_porcentaje'] == pytest.approx(12)
        assert drift['base_comparacion'] == 'VALOR_REFERENCIA'


def test_calibracion_posterior_a_la_captura_no_se_usa(client, db_session, equipo_g165):
    e = equipo_g165
    usuario = db_session.execute(text('SELECT id_usuario FROM modulo1.usuarios ORDER BY id_usuario LIMIT 1')).scalar_one()
    lectura = insertar_serie(db_session, e, [28.0] * 20, 28.0)
    captura = db_session.execute(text('SELECT timestamp_captura FROM modulo3.telemetrias WHERE id_telemetria=:t'),
                                 {'t': lectura}).scalar_one()
    db_session.execute(text('''INSERT INTO modulo9.calibraciones
        (id_sensor,id_dispositivo_iot,fecha_calibracion,valor_referencia,id_usuario,ganancia,offset_calibracion)
        VALUES (:s,:d,:ts,25,:u,1,0)'''),
        {'s': e['sensor'], 'd': e['dispositivo'], 'u': usuario, 'ts': captura + timedelta(hours=1)})
    db_session.commit()

    r = client.post(f'/iot/calidad/{lectura}/evaluar', headers=e['headers'])

    assert r.status_code == 201, r.text
    assert 'posible_drift' not in r.json()['flags_detectados']

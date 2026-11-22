# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-10-31 | Claude | INC-M03-246-G88 RF-58: semáforo con lectura fuera de rango, T configurable y recálculo |
"""INC-M03-246-G88 (#889) con PostgreSQL real, RLS (sgpmp_app) y el router HTTP.

Umbral de la especie del área: 15-30 °C (normal 15-25, precaución 25-28, crítico 28-30),
T por defecto = 10 % del rango = 1.5.
"""
from decimal import Decimal
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text

_spec = importlib.util.spec_from_file_location(
    'g88_base', Path(__file__).with_name('test_issue_678_g87_dashboard_condiciones.py'))
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)

contexto = base.contexto
cliente = base.cliente
pytestmark = pytest.mark.integration


def _umbral(db, ctx):
    return db.execute(text("""
        SELECT ua.id_umbral_ambiental FROM modulo9.umbrales_ambientales ua
        JOIN modulo9.infraestructuras_especies ie ON ie.id_especie = ua.id_especie
        WHERE ie.id_infraestructura = :a AND ua.es_activo"""), {'a': ctx['area']}).scalar_one()


def _semaforo(cliente, ctx):
    r = cliente.get('/iot/monitoreo/dashboard/' + str(ctx['area']), headers=ctx['headers']['Productor'])
    assert r.status_code == 200, r.text
    datos = r.json()
    return datos['sensores'][0], datos['resumen_unidades'][0], datos['conteo_semaforo']


@pytest.mark.parametrize('valor,esperado', [
    (13.65, 'AMARILLO'), (14.85, 'AMARILLO'), (30.15, 'AMARILLO'), (31.35, 'AMARILLO'),  # TC-M03-170
    (13.35, 'ROJO'), (31.65, 'ROJO'),                                                     # TC-M03-171
])
def test_lectura_fuera_de_rango_no_queda_verde(cliente, db_session, contexto, valor, esperado):
    base.validas(db_session, contexto)
    assert base.ingerir(db_session, contexto, valor, 3).estado_calidad == 'FUERA_DE_RANGO'

    sensor, unidad, conteo = _semaforo(cliente, contexto)

    assert sensor['estado_semaforo'] == esperado
    assert unidad['estado_general'] == esperado
    assert conteo == {esperado: 1}
    # Se conservan la referencia válida, el indicador y la etiqueta (G87 / TC-M03-169).
    assert Decimal(sensor['ultimo_valor']) == 25
    assert sensor['indicador_anomalia'] and sensor['etiqueta_estado'] == 'Lectura fuera de rango'
    assert Decimal(sensor['valor_condicion_actual']) == Decimal(str(valor))


def test_lectura_valida_dentro_del_umbral_sigue_verde(cliente, db_session, contexto):
    base.validas(db_session, contexto)
    base.ingerir(db_session, contexto, 20, 3)

    sensor, _, _ = _semaforo(cliente, contexto)

    assert sensor['estado_semaforo'] == 'VERDE' and not sensor['indicador_anomalia']


def test_tolerancia_configurada_prevalece_sobre_la_predeterminada(cliente, db_session, contexto):
    """TC-M03-172: con T=2, 31.9 (a 1.9 del borde) es AMARILLO; con T=1.5 era ROJO."""
    base.validas(db_session, contexto)
    base.ingerir(db_session, contexto, 31.9, 3)
    assert _semaforo(cliente, contexto)[0]['estado_semaforo'] == 'ROJO'

    db_session.execute(text('UPDATE modulo9.umbrales_ambientales SET tolerancia_semaforo = 2 WHERE id_umbral_ambiental = :u'),
                       {'u': _umbral(db_session, contexto)})
    db_session.commit()

    assert _semaforo(cliente, contexto)[0]['estado_semaforo'] == 'AMARILLO'


def test_cambio_de_umbral_recalcula_la_misma_lectura(cliente, db_session, contexto):
    """TC-M03-266: lectura 20 con 15-30 es VERDE; con 25-30 y sin lectura nueva deja de serlo."""
    base.validas(db_session, contexto)
    base.ingerir(db_session, contexto, 20, 3)
    assert _semaforo(cliente, contexto)[0]['estado_semaforo'] == 'VERDE'
    lecturas = db_session.execute(text('SELECT count(*) FROM modulo3.telemetrias WHERE id_sensor = :s'),
                                  {'s': contexto['sensor']}).scalar_one()

    umbral = _umbral(db_session, contexto)
    db_session.execute(text('DELETE FROM modulo9.niveles_alerta_ambientales WHERE id_umbral_ambiental = :u'), {'u': umbral})
    db_session.execute(text('UPDATE modulo9.umbrales_ambientales SET valor_min = 25 WHERE id_umbral_ambiental = :u'), {'u': umbral})
    for nivel, a, b in [('normal', 25, 27), ('precaucion', 27, 28), ('critico', 28, 30)]:
        db_session.execute(text("""INSERT INTO modulo9.niveles_alerta_ambientales
            (id_umbral_ambiental, nivel, limite_inferior, limite_superior) VALUES (:u, :n, :a, :b)"""),
            {'u': umbral, 'n': nivel, 'a': a, 'b': b})
    db_session.commit()

    sensor, unidad, _ = _semaforo(cliente, contexto)
    assert sensor['estado_semaforo'] == 'ROJO'  # 5 por debajo de 25, T = 0.5
    assert unidad['estado_general'] == 'ROJO'
    assert db_session.execute(text('SELECT count(*) FROM modulo3.telemetrias WHERE id_sensor = :s'),
                              {'s': contexto['sensor']}).scalar_one() == lecturas


def test_sin_umbral_sigue_gris_con_su_etiqueta(cliente, db_session, contexto):
    """TC-M03-180: sin umbral activo para la variable, GRIS y 'Sin umbral configurado'."""
    base.validas(db_session, contexto)
    db_session.execute(text('UPDATE modulo9.umbrales_ambientales SET es_activo = false WHERE id_umbral_ambiental = :u'),
                       {'u': _umbral(db_session, contexto)})
    db_session.commit()

    sensor, _, _ = _semaforo(cliente, contexto)

    assert sensor['estado_semaforo'] == 'GRIS' and sensor['sin_umbral']
    assert sensor['etiqueta_estado'] == 'Sin umbral configurado'

# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-130-G16 RF-53/62: reproducir frecuencia y validar drift postcommit con ingesta real y PostgreSQL. |
"""RF-53/RF-62: los datos entran por HTTP o por la función común del broker."""
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from datetime import timedelta

import pytest
from sqlalchemy import text

from src.shared.database import como_sistema
from src.telemetry.infrastructure.routers.telemetria_router import router as telemetria
from src.telemetry.infrastructure.workers.postcommit_worker import _lectura
from tests.integration.test_inc_m03_104_g165_motor_calidad import equipo_g165, rutas_g165
from tests.integration.test_dev05_ingesta_bplus_postcommit import sql_ingesta

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def rutas_g31(integration_app):
    if not any(getattr(r, 'path', None) == '/iot/telemetria' for r in integration_app.routes):
        integration_app.include_router(telemetria)


@pytest.fixture
def equipo_g31(db_session, equipo_g165):
    e = dict(equipo_g165)
    area, serial = db_session.execute(text('''SELECT id_infraestructura,serial
        FROM modulo9.dispositivos_iot WHERE id_dispositivo_iot=:d'''),
        {'d': e['dispositivo']}).one()
    usuario = db_session.execute(text('SELECT min(id_usuario) FROM modulo1.usuarios')).scalar_one()
    db_session.execute(text('''INSERT INTO modulo9.sensores_areas_asociadas
        (id_sensor,id_dispositivo_iot,id_infraestructura,punto_instalacion,tiene_estado,fecha_asociacion,id_usuario)
        VALUES (:s,:d,:a,'G31',true,now()-interval '2 days',:u)'''),
        {'s': e['sensor'], 'd': e['dispositivo'], 'a': area, 'u': usuario})
    db_session.commit()
    e.update(device=e['dispositivo'], serial=serial, usuario=usuario)
    return e


def payload(e, captura, valor=22):
    return {'device_id': e['device'], 'sensor_id': e['sensor'], 'serial': e['serial'],
            'tipo_variable': 'TEMPERATURA_AMBIENTAL', 'valor': valor, 'unidad': '°C',
            'timestamp_captura': captura.isoformat()}


def fila(db, identificador):
    return db.execute(text('SELECT to_jsonb(t) FROM modulo3.telemetrias t WHERE id_telemetria=:id'),
                      {'id': identificador}).scalar_one()


def ingerir(client, db, e, headers, captura, canal, origen='TIEMPO_REAL'):
    if canal == 'sql':
        with como_sistema(db):
            db.execute(text('SET LOCAL ROLE sgpmp_app'))
            try:
                assert db.execute(text('SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user')).scalar_one() is False
                return sql_ingesta(db, e, captura).id_telemetria
            finally:
                db.execute(text('RESET ROLE'))
    body = dict(payload(e, captura), origen=origen)
    r = client.post('/iot/telemetria' if canal == 'http' else '/iot/telemetria/batch',
                    json=body if canal == 'http' else {'registros': [body]}, headers=headers)
    assert r.status_code == (201 if canal == 'http' else 200), r.text
    if canal == 'batch':
        assert r.json()['aceptados'] == 1, r.text
        return r.json()['detalle'][0]['id_telemetria']
    return r.json()['id_telemetria']


@pytest.mark.parametrize('canal', ['http', 'batch', 'sql'])
@pytest.mark.parametrize('minutos,anomalia', [(1, True), (4.99, True), (5, False), (10, False), (20, False), (20.01, True), (60, True)])
def test_frecuencia_rapida_normal_y_lenta_sin_rechazar(
    client, db_session, equipo_g31, headers_broker, canal, minutos, anomalia,
):
    e = equipo_g31
    captura = db_session.execute(text("SELECT now()-interval '1 minute'")).scalar_one()
    anterior = ingerir(client, db_session, e, headers_broker, captura-timedelta(minutes=minutos), canal)
    original = fila(db_session, anterior)
    assert original['frecuencia_anomala'] is False
    actual = ingerir(client, db_session, e, headers_broker, captura, canal)
    resultado = fila(db_session, actual)
    assert resultado['frecuencia_anomala'] is anomalia
    assert resultado['latencia_alta'] is False
    assert original['latencia_alta'] is (minutos + 1 > 10)
    assert fila(db_session, anterior) == original
    assert db_session.execute(text('SELECT count(*) FROM modulo3.bitacora_ingest WHERE id_telemetria=:id'),
                              {'id': actual}).scalar_one() == 1


def test_ingesta_conserva_frecuencia_aplicada_para_rf62(client, db_session, equipo_g31, headers_broker):
    captura = db_session.execute(text("SELECT now()-interval '1 minute'")).scalar_one()
    identificador = ingerir(client, db_session, equipo_g31, headers_broker, captura, 'http')
    assert fila(db_session, identificador)['frecuencia_muestreo_min'] == 10


@pytest.mark.parametrize('offset,esperado', [(0, False), (2, True), (None, False)])
def test_drift_se_calcula_en_rf62_sin_mutar_lecturas(
    client, db_session, equipo_g31, headers_broker, offset, esperado,
):
    e = equipo_g31
    captura = db_session.execute(text("SELECT now()-interval '1 minute'")).scalar_one()
    if offset is not None:
        db_session.execute(text('''INSERT INTO modulo9.calibraciones
            (id_sensor,id_dispositivo_iot,fecha_calibracion,valor_referencia,id_usuario,ganancia,offset_calibracion)
            VALUES (:s,:d,:ts,22,:u,1,:offset)'''),
            {'s': e['sensor'], 'd': e['device'], 'u': e['usuario'],
             'ts': captura-timedelta(days=1), 'offset': offset})
        db_session.commit()
    registros = [payload(e, captura-timedelta(minutes=(20-i)*10), 22+i%2) for i in range(21)]
    r = client.post('/iot/telemetria/batch', json={'registros': registros}, headers=headers_broker)
    assert r.status_code == 200 and r.json()['aceptados'] == 21, r.text
    identificador = r.json()['detalle'][-1]['id_telemetria']
    antes = db_session.execute(text('SELECT jsonb_agg(to_jsonb(t) ORDER BY id_telemetria) FROM modulo3.telemetrias t WHERE id_sensor=:s'),
                               {'s': e['sensor']}).scalar_one()
    assert all(t['posible_drift'] is False for t in antes)
    with como_sistema(db_session):
        db_session.execute(text('SET LOCAL ROLE sgpmp_app'))
        try:
            _lectura(db_session).evaluar_lectura(identificador)
        finally:
            db_session.execute(text('RESET ROLE'))
    detalle = client.get(f'/iot/calidad/{identificador}', headers=e['headers'])
    assert detalle.status_code == 200, detalle.text
    ev = detalle.json()
    assert bool(ev['flags_detectados'].get('posible_drift', {}).get('activo')) is esperado
    assert ev['parametros_calibracion_aplicados'] == (None if offset is None else {'ganancia': 1, 'offset': offset})
    if esperado:
        drift = ev['flags_detectados']['posible_drift']
        assert drift['magnitud_drift_porcentaje'] > 5
        assert drift['P_lecturas_consistentes'] >= 5
    if offset is None:
        assert ev['flags_detectados']['calibracion_no_disponible']['activo'] is True
        assert ev['clasificacion_calidad'] == 'INDETERMINADA'
    assert db_session.execute(text('SELECT jsonb_agg(to_jsonb(t) ORDER BY id_telemetria) FROM modulo3.telemetrias t WHERE id_sensor=:s'),
                              {'s': e['sensor']}).scalar_one() == antes
    assert db_session.execute(text("SELECT count(*) FROM modulo3.telemetria_calidad WHERE id_telemetria=:id AND estado_evaluacion='VIGENTE'"),
                              {'id': identificador}).scalar_one() == 1


@pytest.mark.parametrize('canal', ['http', 'batch'])
@pytest.mark.parametrize('minutos,esperado', [(10, False), (59, True), (120, True)])
def test_buffer_fuera_de_orden_usa_vecino_mas_cercano_y_conserva_historial(
    client, db_session, equipo_g31, headers_broker, canal, minutos, esperado,
):
    e = equipo_g31
    inicio = db_session.execute(text("SELECT now()-interval '4 hours'")).scalar_one()
    ids = [ingerir(client, db_session, e, headers_broker, inicio+timedelta(minutes=i),
                   canal, 'BUFFER_LOCAL') for i in (0, 60)]
    originales = [fila(db_session, i) for i in ids]
    assert originales[1]['frecuencia_anomala'] is True
    actual = ingerir(client, db_session, e, headers_broker, inicio+timedelta(minutes=minutos),
                     canal, 'BUFFER_LOCAL')
    assert fila(db_session, actual)['frecuencia_anomala'] is esperado
    assert [fila(db_session, i) for i in ids] == originales


def test_rf62_usa_muestreo_historico_aunque_cambie_configuracion(
    client, db_session, equipo_g31, headers_broker,
):
    e = equipo_g31
    captura = db_session.execute(text("SELECT now()-interval '1 minute'")).scalar_one()
    db_session.execute(text('''INSERT INTO modulo9.calibraciones
        (id_sensor,id_dispositivo_iot,fecha_calibracion,valor_referencia,id_usuario,ganancia,offset_calibracion)
        VALUES (:s,:d,:ts,22,:u,1,0)'''),
        {'s': e['sensor'], 'd': e['device'], 'u': e['usuario'], 'ts': captura-timedelta(days=1)})
    db_session.commit()
    registros = [payload(e, captura-timedelta(minutes=(20-i)*10), 22+i%2) for i in range(21)]
    r = client.post('/iot/telemetria/batch', json={'registros': registros}, headers=headers_broker)
    assert r.status_code == 200 and r.json()['aceptados'] == 21, r.text
    identificador = r.json()['detalle'][-1]['id_telemetria']
    antes = fila(db_session, identificador)
    assert antes['frecuencia_muestreo_min'] == 10
    db_session.execute(text('UPDATE modulo9.configuraciones_globales SET frecuencia_muestreo=60,heartbeat=120 WHERE es_activo'))
    db_session.commit()
    r = client.post(f'/iot/calidad/{identificador}/evaluar', headers=e['headers'])
    assert r.status_code == 201, r.text
    assert r.json()['parametros_aplicados']['consistencia_temporal']['frecuencia_muestreo_min'] == 10
    assert fila(db_session, identificador) == antes


def test_migracion_reversible_preserva_funcion_y_atributos(db_session):
    ruta = Path(__file__).parents[2]/'alembic/versions/c685130a0260_frecuencia_anomala_ingesta.py'
    spec = importlib.util.spec_from_file_location('migracion_g31', ruta)
    migracion = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migracion)
    definicion = text('SELECT pg_get_functiondef(CAST(:firma AS regprocedure))')
    propiedades = text('''SELECT proowner,proacl,prosecdef,proconfig,provolatile,proparallel
        FROM pg_proc WHERE oid=CAST(:firma AS regprocedure)''')
    params = {'firma': migracion.FN}
    actual = db_session.execute(definicion, params).scalar_one()
    atributos = db_session.execute(propiedades, params).one()
    assert 'G167_SNAPSHOT_VALOR' in actual and 'v_ids_especies' in actual
    with Operations.context(MigrationContext.configure(db_session.connection())):
        migracion.downgrade()
        anterior = db_session.execute(definicion, params).scalar_one()
        assert 'G31_FRECUENCIA_' not in anterior
        assert 'RFC053_B_INICIO' in anterior
        assert db_session.execute(propiedades, params).one() == atributos
        migracion.upgrade()
        assert db_session.execute(definicion, params).scalar_one() == actual
        assert db_session.execute(propiedades, params).one() == atributos
        with pytest.raises(RuntimeError, match='bloque esperado'):
            migracion.upgrade()
        assert db_session.execute(definicion, params).scalar_one() == actual
        # El parche completo no puede cambiar otras reglas ni los snapshots.
        assert migracion._transformar(anterior) == actual
        assert migracion._transformar(actual, revertir=True) == anterior


def test_frecuencia_declarada_por_cliente_no_reemplaza_configuracion_m09(
    client, db_session, equipo_g31, headers_broker,
):
    e = equipo_g31
    captura = db_session.execute(text("SELECT now()-interval '1 minute'")).scalar_one()
    ingerir(client, db_session, e, headers_broker, captura-timedelta(minutes=1), 'http')
    r = client.post('/iot/telemetria', json=dict(payload(e,captura),frecuencia_muestreo=1), headers=headers_broker)
    assert r.status_code == 201, r.text
    lectura = fila(db_session, r.json()['id_telemetria'])
    assert lectura['frecuencia_anomala'] is True
    assert lectura['frecuencia_muestreo_min'] == 10


def test_eventos_no_periodicos_no_falsean_frecuencia_de_lecturas(
    client, db_session, equipo_g31, headers_broker,
):
    e = equipo_g31
    captura = db_session.execute(text("SELECT now()-interval '1 minute'")).scalar_one()
    anterior = ingerir(client, db_session, e, headers_broker, captura-timedelta(minutes=10), 'http')
    # Un EVENTO_EDGE no es una muestra periódica. Prepararlo en la misma tabla
    # permite comprobar que no altera el intervalo del sensor/variable.
    db_session.execute(text('''INSERT INTO modulo3.telemetrias
        (id_sensor,id_variable,id_dispositivo_iot,valor_crudo,timestamp_captura,
         timestamp_procesamiento,origen,estado_calidad,calibrado,categoria_variable,
         unidad_medida,valor_agregado,tipo_dato,metadatos)
        VALUES (:s,9,:d,22,:ts,now(),'TIEMPO_REAL','ERROR_CALIBRACION',false,
                'AMBIENTAL','°C',false,'EVENTO_EDGE','{}')'''),
        {'s':e['sensor'],'d':e['device'],'ts':captura-timedelta(minutes=1)})
    db_session.commit()
    original = fila(db_session,anterior)
    actual = ingerir(client, db_session, e, headers_broker, captura,'http')
    assert fila(db_session,actual)['frecuencia_anomala'] is False
    assert fila(db_session,anterior) == original

# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-131-G23 RF-53/54: verificar persistencia exacta, FIFO observable, compatibilidad, deduplicacion y rollback en PostgreSQL. |
"""Ingesta real y rol API; no certifica el orden de envío físico del nodo Edge."""
from datetime import timedelta

import pytest
from sqlalchemy import text

from src.shared.database import como_sistema
from src.shared.errors import ServiceUnavailableError
from src.telemetry.infrastructure.repositories.ingesta_telemetria_repository import SqlAlchemyIngestaTelemetriaRepository
from src.telemetry.infrastructure.repositories.telemetria_repository import SqlAlchemyTelemetriaRepository
from src.telemetry.infrastructure.routers.telemetria_router import router
from tests.integration.test_dev05_ingesta_bplus_postcommit import hardware, modelos

pytestmark = pytest.mark.integration
MAX_LONG = 2**63-1


@pytest.fixture(autouse=True)
def rutas_g23(integration_app):
    if not any(getattr(r,'path',None)=='/iot/telemetria' for r in integration_app.routes):
        integration_app.include_router(router)


@pytest.fixture
def equipo_g23(db_session):
    e = hardware(db_session)
    e['captura'] = db_session.execute(text("SELECT now()-interval '1 minute'")).scalar_one()
    return e


def payload(e, secuencia=None, *, minutos=0):
    body = {'device_id':e['device'],'sensor_id':e['sensor'],'serial':e['serial'],
            'tipo_variable':'TEMPERATURA_AMBIENTAL','valor':22,'unidad':'°C',
            'timestamp_captura':(e['captura']-timedelta(minutes=minutos)).isoformat(),
            'origen':'BUFFER_LOCAL'}
    if secuencia is not None:
        body['buffer_sequence_id'] = secuencia
    return body


def lecturas(db,e):
    return db.execute(text('''SELECT id_telemetria,metadatos,timestamp_captura,origen,
        jsonb_typeof(metadatos->'buffer_sequence_id') AS tipo_secuencia
        FROM modulo3.telemetrias WHERE id_sensor=:s ORDER BY id_telemetria'''),
        {'s':e['sensor']}).mappings().all()


@pytest.mark.parametrize('secuencia',[None,0,37,MAX_LONG])
def test_http_conserva_identificador_original_y_lectura_de_dominio(
    client,db_session,equipo_g23,headers_broker,secuencia,
):
    e = equipo_g23
    r = client.post('/iot/telemetria',json=payload(e,secuencia),headers=headers_broker)
    assert r.status_code == 201,r.text
    assert set(r.json()) == {'id_telemetria','estado_calidad','timestamp_procesamiento','latencia_procesamiento_ms'}
    fila = lecturas(db_session,e)[0]
    assert fila['origen'] == 'BUFFER_LOCAL'
    assert fila['timestamp_captura'] == e['captura']
    assert fila['metadatos'].get('buffer_sequence_id') == secuencia
    assert fila['tipo_secuencia'] == (None if secuencia is None else 'number')
    if secuencia is None:
        assert 'buffer_sequence_id' not in fila['metadatos']
    entidad = SqlAlchemyTelemetriaRepository(db_session).obtener_por_id(r.json()['id_telemetria'])
    assert entidad.metadatos == fila['metadatos']


def test_batch_desordenado_conserva_secuencia_por_lectura_y_orden_cronologico(
    client,db_session,equipo_g23,headers_broker,
):
    e = equipo_g23
    registros = [payload(e,103),payload(e,101,minutos=20),payload(e,102,minutos=10)]
    r = client.post('/iot/telemetria/batch',json={'registros':registros},headers=headers_broker)
    assert r.status_code == 200,r.text
    assert (r.json()['aceptados'],r.json()['rechazados'],r.json()['duplicados']) == (3,0,0)
    filas = lecturas(db_session,e)
    assert [f['metadatos']['buffer_sequence_id'] for f in filas] == [101,102,103]
    assert [f['timestamp_captura'] for f in filas] == sorted(f['timestamp_captura'] for f in filas)
    assert [f['id_telemetria'] for f in filas] == [f['id_telemetria'] for f in r.json()['detalle']]
    # SQL disponible para QA sin depender del orden físico de filas.
    assert db_session.execute(text('''SELECT (metadatos->>'buffer_sequence_id')::bigint
        FROM modulo3.telemetrias WHERE id_sensor=:s ORDER BY timestamp_captura,id_telemetria'''),
        {'s':e['sensor']}).scalars().all() == [101,102,103]


def test_secuencia_no_reemplaza_clave_de_deduplicacion_ni_modifica_original(
    client,db_session,equipo_g23,headers_broker,
):
    e = equipo_g23
    primero = client.post('/iot/telemetria',json=payload(e,101,minutos=10),headers=headers_broker)
    assert primero.status_code == 201,primero.text
    antes = dict(lecturas(db_session,e)[0])
    repetido = client.post('/iot/telemetria',json=payload(e,999,minutos=10),headers=headers_broker)
    assert repetido.status_code == 409,repetido.text
    assert repetido.json()['error_code'] == 'ERROR_DUPLICADO'
    assert dict(lecturas(db_session,e)[0]) == antes
    batch = client.post('/iot/telemetria/batch',json={'registros':[
        payload(e,101,minutos=10),payload(e,102)]},headers=headers_broker)
    assert batch.status_code == 200,batch.text
    assert (batch.json()['aceptados'],batch.json()['duplicados']) == (1,1)
    assert [f['metadatos']['buffer_sequence_id'] for f in lecturas(db_session,e)] == [101,102]


def test_secuencia_no_se_supone_globalmente_unica(
    client,db_session,equipo_g23,headers_broker,
):
    e = equipo_g23
    otro = dict(hardware(db_session),captura=e['captura'])
    for equipo in (e,otro):
        r = client.post('/iot/telemetria',json=payload(equipo,1),headers=headers_broker)
        assert r.status_code == 201,r.text
    assert lecturas(db_session,e)[0]['metadatos']['buffer_sequence_id'] == 1
    assert lecturas(db_session,otro)[0]['metadatos']['buffer_sequence_id'] == 1


@pytest.mark.parametrize('secuencia',[-1,MAX_LONG+1,True,1.5,'7'])
def test_identificador_invalido_es_400_y_no_se_persiste(
    client,db_session,equipo_g23,headers_broker,secuencia,
):
    e = equipo_g23
    r = client.post('/iot/telemetria',json=payload(e,secuencia),headers=headers_broker)
    assert r.status_code == 400,r.text
    assert r.json()['error_code'] == 'VAL_ENTRADA'
    assert lecturas(db_session,e) == []


def test_funcion_comun_del_broker_conserva_metadato_sin_cambiar_su_firma(db_session,equipo_g23):
    e = equipo_g23
    with como_sistema(db_session):
        db_session.execute(text('SET LOCAL ROLE sgpmp_app'))
        try:
            assert db_session.execute(text('SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user')).scalar_one() is False
            r = SqlAlchemyIngestaTelemetriaRepository(db_session).ingerir({
                'device_id':e['device'],'sensor_id':e['sensor'],'id_variable':9,'valor':22,
                'unidad':'°C','timestamp_captura':e['captura'],'timestamp_envio':e['captura'],
                'origen':'BUFFER_LOCAL','categoria':'AMBIENTAL','tipo_dato':'CRUDO',
                'valor_agregado':False,'ventana_agregacion':None,'latitud':None,'longitud':None,
                'nivel_bateria':None,'calidad_senal_rssi':None,'calidad_senal_snr':None,
                'estado_conectividad':False,'metadatos':{'buffer_sequence_id':MAX_LONG,'gateway_id':'G23'},
            })
            db_session.commit()
        finally:
            db_session.execute(text('RESET ROLE'))
    assert r.id_telemetria is not None
    fila = lecturas(db_session,e)[0]
    assert fila['metadatos'] == {'buffer_sequence_id':MAX_LONG,'gateway_id':'G23'}
    assert fila['tipo_secuencia'] == 'number'


def test_fallo_de_commit_revierte_lectura_y_secuencia_y_permite_reintento(
    client,db_session,equipo_g23,headers_broker,monkeypatch,
):
    e = equipo_g23
    primera = client.post('/iot/telemetria',json=payload(e,10,minutos=10),headers=headers_broker)
    assert primera.status_code == 201,primera.text
    original = dict(lecturas(db_session,e)[0])
    observadas = []

    def fallar_commit():
        filas = lecturas(db_session,e)
        observadas.append([f['metadatos']['buffer_sequence_id'] for f in filas])
        raise ServiceUnavailableError('PERSISTENCIA_NO_CONFIRMADA','No fue posible confirmar la lectura.')

    with monkeypatch.context() as cambios:
        cambios.setattr(db_session,'commit',fallar_commit)
        r = client.post('/iot/telemetria',json=payload(e,11),headers=headers_broker)
    assert observadas == [[10,11]],observadas
    assert r.status_code == 503,r.text
    assert lecturas(db_session,e) == [original]
    r = client.post('/iot/telemetria',json=payload(e,11),headers=headers_broker)
    assert r.status_code == 201,r.text
    assert [f['metadatos']['buffer_sequence_id'] for f in lecturas(db_session,e)] == [10,11]


def test_token_de_servicio_sigue_siendo_obligatorio(client,db_session,equipo_g23,headers_broker):
    r = client.post('/iot/telemetria',json=payload(equipo_g23,1))
    assert r.status_code == 401,r.text
    assert lecturas(db_session,equipo_g23) == []


def test_backend_conserva_secuencia_original_aunque_no_coincida_con_timestamps(
    client,db_session,equipo_g23,headers_broker,
):
    e = equipo_g23
    r = client.post('/iot/telemetria/batch',json={'registros':[
        payload(e,11),payload(e,12,minutos=10)]},headers=headers_broker)
    assert r.status_code == 200 and r.json()['aceptados'] == 2,r.text
    # La trazabilidad debe conservar la evidencia recibida; no renumerarla
    # para aparentar un orden FIFO del Edge que no ha sido observado.
    assert [f['metadatos']['buffer_sequence_id'] for f in lecturas(db_session,e)] == [12,11]

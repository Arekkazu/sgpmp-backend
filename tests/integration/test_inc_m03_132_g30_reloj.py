# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-132-G30 RF-53/54/62: reproducir marca TIME_DESYNC al insertar con evidencia de heartbeat en PostgreSQL real. |
# | 2026-10-28 | Arekkazu | INC-M03-132-G30 RF-54: acepta el bloque de frecuencia de G16 al revertir |
"""La función SQL compartida determina el snapshot antes del INSERT inmutable."""
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from datetime import timedelta

import pytest
from sqlalchemy import text

from src.shared.database import como_sistema
from src.shared.errors import ServiceUnavailableError
from src.telemetry.application.use_cases.calidad.evaluar_calidad_telemetria_use_case import EvaluarCalidadTelemetriaUseCase
from src.telemetry.infrastructure.repositories.ingesta_telemetria_repository import SqlAlchemyIngestaTelemetriaRepository
from src.telemetry.infrastructure.routers.telemetria_router import router
from src.telemetry.infrastructure.routers.calidad_router import router as calidad
from src.telemetry.infrastructure.workers.postcommit_worker import _lectura
from src.configuration.application.use_cases.configuracion_global.configurar_parametros_mlops_use_case import ConfigurarParametrosMLOpsUseCase
from src.prediction.infrastructure.repositories.parametros_mlops_repository import SqlAlchemyParametrosMLOpsRepository
from tests.integration.test_dev05_ingesta_bplus_postcommit import hardware, modelos

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def rutas_g30(integration_app):
    for rtr in (router,calidad):
        if not any(getattr(r,'path',None)==rtr.routes[0].path for r in integration_app.routes):
            integration_app.include_router(rtr)


@pytest.fixture
def equipo_g30(db_session):
    e = hardware(db_session)
    e['captura'] = db_session.execute(text("SELECT now()-interval '1 minute'")).scalar_one()
    return e


def heartbeat(db,e,sincronizado,*,minutos=2):
    ts = e['captura']-timedelta(minutes=minutos)
    identificador = db.execute(text('''INSERT INTO modulo3.heartbeats
        (id_dispositivo_iot,tipo_mensaje,fecha_registro,fecha_recepcion,reloj_sincronizado)
        VALUES (:d,'HEARTBEAT',:ts,:ts,:sincronizado) RETURNING id_heartbeat'''),
        {'d':e['device'],'ts':ts,'sincronizado':sincronizado}).scalar_one()
    db.commit()
    return identificador


def payload(e,**cambios):
    return dict({'device_id':e['device'],'sensor_id':e['sensor'],'serial':e['serial'],
        'tipo_variable':'TEMPERATURA_AMBIENTAL','valor':22,'unidad':'°C',
        'timestamp_captura':e['captura'].isoformat(),'origen':'BUFFER_LOCAL'},**cambios)


def fila(db,identificador):
    return db.execute(text('SELECT to_jsonb(t) FROM modulo3.telemetrias t WHERE id_telemetria=:id'),
                      {'id':identificador}).scalar_one()


def test_heartbeat_desincronizado_se_propaga_al_insert_de_telemetria(
    client,db_session,equipo_g30,headers_broker,
):
    e = equipo_g30
    hb = heartbeat(db_session,e,False)
    r = client.post('/iot/telemetria',json=payload(e),headers=headers_broker)
    assert r.status_code == 201,r.text
    lectura = fila(db_session,r.json()['id_telemetria'])
    assert lectura['reloj_desincronizado'] is True
    assert lectura['metadatos']['rf53_reloj']['fuente'] == 'HEARTBEAT'
    assert lectura['metadatos']['rf53_reloj']['id_heartbeat'] == hb


@pytest.mark.parametrize('hb,explicito,esperado,fuente',[
    (True,None,False,'HEARTBEAT'),(False,None,True,'HEARTBEAT'),
    (True,False,True,'LECTURA'),(False,True,False,'LECTURA'),
    (None,False,True,'LECTURA'),(None,True,False,'LECTURA'),
    (None,None,False,'SIN_EVIDENCIA'),
])
def test_precedencia_de_evidencia_y_ausencia_no_inventan_sincronizacion(
    client,db_session,equipo_g30,headers_broker,hb,explicito,esperado,fuente,
):
    e = equipo_g30
    if hb is not None:
        heartbeat(db_session,e,hb)
    r = client.post('/iot/telemetria',json=payload(e,reloj_sincronizado=explicito),headers=headers_broker)
    assert r.status_code == 201,r.text
    l = fila(db_session,r.json()['id_telemetria'])
    assert l['reloj_desincronizado'] is esperado
    evidencia = l['metadatos']['rf53_reloj']
    assert evidencia['fuente'] == fuente
    assert evidencia['codigo'] == ('TIME_DESYNC' if esperado else None)
    assert evidencia['reloj_sincronizado'] is (explicito if explicito is not None else hb)
    if fuente != 'HEARTBEAT':
        assert evidencia['id_heartbeat'] is None


def test_ultimo_heartbeat_por_recepcion_desempata_por_id_y_no_modifica_lecturas_previas(
    client,db_session,equipo_g30,headers_broker,
):
    e = equipo_g30
    primero = heartbeat(db_session,e,False)
    r = client.post('/iot/telemetria',json=payload(e),headers=headers_broker)
    assert r.status_code == 201,r.text
    antes = fila(db_session,r.json()['id_telemetria'])
    assert antes['reloj_desincronizado'] is True
    segundo = heartbeat(db_session,e,True)  # misma fecha de recepción, ID posterior
    assert segundo > primero
    r = client.post('/iot/telemetria',json=payload(e,timestamp_captura=(e['captura']+timedelta(seconds=10)).isoformat()),headers=headers_broker)
    assert r.status_code == 201,r.text
    actual = fila(db_session,r.json()['id_telemetria'])
    assert actual['reloj_desincronizado'] is False
    assert actual['metadatos']['rf53_reloj']['id_heartbeat'] == segundo
    assert fila(db_session,antes['id_telemetria']) == antes


def test_buffer_con_snapshot_desincronizado_no_se_limpia_por_heartbeat_recuperado(
    client,db_session,equipo_g30,headers_broker,
):
    e = equipo_g30
    heartbeat(db_session,e,True)
    r = client.post('/iot/telemetria/batch',json={'registros':[
        payload(e,reloj_sincronizado=False,timestamp_captura=(e['captura']-timedelta(hours=10)).isoformat()),
        payload(e,reloj_sincronizado=True)]},headers=headers_broker)
    assert r.status_code == 200 and r.json()['aceptados']==2,r.text
    ids = [x['id_telemetria'] for x in r.json()['detalle']]
    assert [fila(db_session,i)['reloj_desincronizado'] for i in ids] == [True,False]
    assert all(fila(db_session,i)['metadatos']['rf53_reloj']['fuente']=='LECTURA' for i in ids)


def test_heartbeat_futuro_de_servidor_y_otros_dispositivos_no_se_utilizan(
    client,db_session,equipo_g30,headers_broker,
):
    e = equipo_g30
    otro = dict(hardware(db_session),captura=e['captura'])
    heartbeat(db_session,otro,False)
    heartbeat(db_session,e,False,minutos=-5)
    r = client.post('/iot/telemetria',json=payload(e),headers=headers_broker)
    assert r.status_code == 201,r.text
    l = fila(db_session,r.json()['id_telemetria'])
    assert l['reloj_desincronizado'] is False
    assert l['metadatos']['rf53_reloj']['fuente']=='SIN_EVIDENCIA'
    assert l['metadatos']['rf53_reloj']['reloj_sincronizado'] is None


@pytest.mark.parametrize('valor',[0,'false',[],{}])
def test_http_rechaza_senal_de_reloj_no_booleana(client,db_session,equipo_g30,headers_broker,valor):
    r = client.post('/iot/telemetria',json=payload(equipo_g30,reloj_sincronizado=valor),headers=headers_broker)
    assert r.status_code == 400,r.text
    assert r.json()['error_code']=='VAL_ENTRADA'
    assert db_session.execute(text('SELECT count(*) FROM modulo3.telemetrias WHERE id_sensor=:s'),{'s':equipo_g30['sensor']}).scalar_one()==0


def sql_ingesta_reloj(db,e,meta):
    with como_sistema(db):
        db.execute(text('SET LOCAL ROLE sgpmp_app'))
        try:
            assert db.execute(text('SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user')).scalar_one() is False
            r = SqlAlchemyIngestaTelemetriaRepository(db).ingerir({
                'device_id':e['device'],'sensor_id':e['sensor'],'id_variable':9,'valor':22,
                'unidad':'°C','timestamp_captura':e['captura'],'timestamp_envio':e['captura'],
                'origen':'BUFFER_LOCAL','categoria':'AMBIENTAL','tipo_dato':'CRUDO',
                'valor_agregado':False,'ventana_agregacion':None,'latitud':None,'longitud':None,
                'nivel_bateria':None,'calidad_senal_rssi':None,'calidad_senal_snr':None,
                'estado_conectividad':False,'metadatos':meta,
            })
            db.commit()
            return r
        finally:
            db.execute(text('RESET ROLE'))


@pytest.mark.parametrize('valor',[False,True,None,'false'])
def test_funcion_comun_broker_valida_senal_y_conserva_otros_metadatos(db_session,equipo_g30,valor):
    e = equipo_g30
    heartbeat(db_session,e,False)
    r = sql_ingesta_reloj(db_session,e,{'reloj_sincronizado':valor,'buffer_sequence_id':37})
    if valor == 'false':
        assert r.id_telemetria is None
        assert r.mensaje.startswith('ERROR_ESTRUCTURA:')
        assert db_session.execute(text("SELECT count(*) FROM modulo3.bitacora_ingest WHERE id_sensor=:s AND estado_calidad='ERROR_ESTRUCTURA'"),{'s':e['sensor']}).scalar_one()==1
    else:
        assert r.id_telemetria is not None
        l = fila(db_session,r.id_telemetria)
        assert l['reloj_desincronizado'] is (valor is not True)
        assert l['metadatos']['buffer_sequence_id']==37


@pytest.fixture
def calidad_g30(db_session,equipo_g30,crear_usuario_db,crear_auth_headers):
    e = equipo_g30
    admin = crear_usuario_db(id_rol=1)
    e['headers'] = crear_auth_headers(admin)
    ConfigurarParametrosMLOpsUseCase(db_session,SqlAlchemyParametrosMLOpsRepository(db_session)).execute(
        {'rf62_k':3,'rf62_m':5,'rf62_n':20,'rf62_p':5,'rf62_umbral_drift':5},admin['id_usuario'])
    db_session.execute(text('UPDATE modulo9.configuraciones_globales SET es_activo=false WHERE es_activo'))
    db_session.execute(text('''INSERT INTO modulo9.configuraciones_globales
        (frecuencia_muestreo,heartbeat,fecha_actualizacion,id_usuario,es_activo)
        VALUES (10,20,now(),:u,true)'''),{'u':admin['id_usuario']})
    db_session.execute(text('''INSERT INTO modulo9.calibraciones
        (id_sensor,id_dispositivo_iot,fecha_calibracion,valor_referencia,id_usuario,ganancia,offset_calibracion)
        VALUES (:s,:d,:ts,22,:u,1,0)'''),
        {'s':e['sensor'],'d':e['device'],'ts':e['captura']-timedelta(days=1),'u':admin['id_usuario']})
    db_session.commit()
    return e


@pytest.mark.parametrize('canal',['http','postcommit'])
@pytest.mark.parametrize('sincronizado',[False,True])
def test_calidad_oficial_excluye_time_desync_sin_cambiar_indice_y_conserva_snapshot(
    client,db_session,calidad_g30,headers_broker,canal,sincronizado,
):
    e = calidad_g30
    registros = [payload(e,reloj_sincronizado=True,valor=22+i%2,
        timestamp_captura=(e['captura']-timedelta(minutes=(20-i)*10)).isoformat()) for i in range(20)]
    registros.append(payload(e,reloj_sincronizado=sincronizado,valor=22))
    r = client.post('/iot/telemetria/batch',json={'registros':registros},headers=headers_broker)
    assert r.status_code == 200 and r.json()['aceptados']==21,r.text
    identificador = r.json()['detalle'][-1]['id_telemetria']
    antes = fila(db_session,identificador)
    if canal == 'http':
        r = client.post(f'/iot/calidad/{identificador}/evaluar',headers=e['headers'])
        assert r.status_code == 201,r.text
    else:
        with como_sistema(db_session):
            db_session.execute(text('SET LOCAL ROLE sgpmp_app'))
            try:
                _lectura(db_session).evaluar_lectura(identificador)
            finally:
                db_session.execute(text('RESET ROLE'))
    r = client.get(f'/iot/calidad/{identificador}',headers=e['headers'])
    assert r.status_code == 200,r.text
    ev = r.json()
    assert (ev['indice_calidad'],ev['clasificacion_calidad']) == (100,'APTO')
    assert (ev['apto_para_ia'],ev['apto_para_nic41']) == (sincronizado,sincronizado)
    assert bool(ev['flags_detectados'].get('reloj_desincronizado',{}).get('activo')) is (not sincronizado)
    if not sincronizado:
        assert ev['parametros_aplicados']['restriccion_temporal']['descuento_indice']==0
        assert ev['flags_detectados']['reloj_desincronizado']['codigo']=='TIME_DESYNC'
    heartbeat(db_session,e,True,minutos=0)
    repetida = client.post(f'/iot/calidad/{identificador}/evaluar',headers=e['headers'])
    assert repetida.status_code == 201,repetida.text
    assert (repetida.json()['apto_para_ia'],repetida.json()['apto_para_nic41']) == (sincronizado,sincronizado)
    assert fila(db_session,identificador)==antes
    assert db_session.execute(text("SELECT count(*) FROM modulo3.telemetria_calidad WHERE id_telemetria=:id"),{'id':identificador}).scalar_one()==2
    assert db_session.execute(text("SELECT count(*) FROM modulo3.telemetria_calidad WHERE id_telemetria=:id AND estado_evaluacion='VIGENTE'"),{'id':identificador}).scalar_one()==1


@pytest.mark.parametrize('delta',[timedelta(minutes=2),timedelta(hours=-73)])
def test_marca_no_relaja_rechazos_temporales_existentes(client,db_session,equipo_g30,headers_broker,delta):
    e = equipo_g30
    # La asociacion debe cubrir la captura para alcanzar la validacion temporal.
    db_session.execute(text('UPDATE modulo9.sensores_areas_asociadas SET fecha_asociacion=:ts WHERE id_sensor=:s'),
                       {'ts':e['captura']-timedelta(days=5),'s':e['sensor']})
    db_session.commit()
    r = client.post('/iot/telemetria',json=payload(e,reloj_sincronizado=False,
        timestamp_captura=(e['captura']+delta).isoformat()),headers=headers_broker)
    assert r.status_code==400,r.text
    assert r.json()['error_code']=='ERROR_TIEMPO'
    assert db_session.execute(text('SELECT count(*) FROM modulo3.telemetrias WHERE id_sensor=:s'),{'s':e['sensor']}).scalar_one()==0


def test_migracion_reversible_conserva_funcion_y_privilegios(db_session):
    ruta = Path(__file__).parents[2]/'alembic/versions/c687132a0270_time_desync_ingesta.py'
    spec = importlib.util.spec_from_file_location('migracion_reloj_g30',ruta)
    m = importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    q = text('SELECT pg_get_functiondef(CAST(:f AS regprocedure))')
    p = {'f':m.FN}
    atributos = text('SELECT proowner,proacl,prosecdef,proconfig,provolatile,proparallel FROM pg_proc WHERE oid=CAST(:f AS regprocedure)')
    actual = db_session.execute(q,p).scalar_one()
    original = db_session.execute(atributos,p).one()
    with Operations.context(MigrationContext.configure(db_session.connection())):
        m.downgrade()
        antes = db_session.execute(q,p).scalar_one()
        assert 'G33_RELOJ_' not in antes
        # El bloque de frecuencia es RFC053_B, o G31_FRECUENCIA si ya corrió G16 (#811).
        assert 'G167_SNAPSHOT_VALOR' in antes and ('RFC053_B_INICIO' in antes or 'G31_FRECUENCIA_INICIO' in antes)
        assert db_session.execute(atributos,p).one()==original
        m.upgrade()
        assert db_session.execute(q,p).scalar_one()==actual
        assert db_session.execute(atributos,p).one()==original
        with pytest.raises(RuntimeError,match='ya contiene'):
            m.upgrade()
        assert db_session.execute(q,p).scalar_one()==actual


def test_reloj_futuro_del_heartbeat_forzado_a_false_es_evidencia_de_desincronizacion(
    client,db_session,equipo_g30,headers_broker,
):
    e = equipo_g30
    hb = db_session.execute(text('''INSERT INTO modulo3.heartbeats
        (id_dispositivo_iot,tipo_mensaje,fecha_registro,fecha_recepcion,reloj_sincronizado)
        VALUES (:d,'HEARTBEAT',:registro,:recepcion,true) RETURNING id_heartbeat'''),
        {'d':e['device'],'registro':e['captura']+timedelta(hours=2),
         'recepcion':e['captura']-timedelta(minutes=1)}).scalar_one()
    db_session.commit()
    assert db_session.execute(text('SELECT reloj_sincronizado FROM modulo3.heartbeats WHERE id_heartbeat=:id'),{'id':hb}).scalar_one() is False
    r = client.post('/iot/telemetria',json=payload(e),headers=headers_broker)
    assert r.status_code==201,r.text
    l = fila(db_session,r.json()['id_telemetria'])
    assert l['reloj_desincronizado'] is True
    assert l['metadatos']['rf53_reloj']['id_heartbeat']==hb


def test_rollback_de_ingesta_no_deja_marca_ni_lectura_y_permite_reintento(
    client,db_session,equipo_g30,headers_broker,monkeypatch,
):
    e = equipo_g30
    heartbeat(db_session,e,False)
    observadas = []

    def fallar_commit():
        observadas.extend(db_session.execute(text('SELECT reloj_desincronizado FROM modulo3.telemetrias WHERE id_sensor=:s'),{'s':e['sensor']}).scalars())
        raise ServiceUnavailableError('PERSISTENCIA_NO_CONFIRMADA','No fue posible confirmar la lectura.')

    with monkeypatch.context() as cambios:
        cambios.setattr(db_session,'commit',fallar_commit)
        r = client.post('/iot/telemetria',json=payload(e),headers=headers_broker)
    assert r.status_code==503,r.text
    assert observadas==[True]
    assert db_session.execute(text('SELECT count(*) FROM modulo3.telemetrias WHERE id_sensor=:s'),{'s':e['sensor']}).scalar_one()==0
    r = client.post('/iot/telemetria',json=payload(e),headers=headers_broker)
    assert r.status_code==201,r.text
    assert fila(db_session,r.json()['id_telemetria'])['reloj_desincronizado'] is True


def test_fallo_de_auditoria_no_confirma_calidad_y_conserva_snapshot_para_reintento(
    client,db_session,calidad_g30,headers_broker,monkeypatch,
):
    e = calidad_g30
    registros = [payload(e,reloj_sincronizado=True,valor=22+i%2,
        timestamp_captura=(e['captura']-timedelta(minutes=(20-i)*10)).isoformat()) for i in range(20)]
    registros.append(payload(e,reloj_sincronizado=False))
    r = client.post('/iot/telemetria/batch',json={'registros':registros},headers=headers_broker)
    assert r.status_code==200 and r.json()['aceptados']==21,r.text
    identificador = r.json()['detalle'][-1]['id_telemetria']
    antes = fila(db_session,identificador)
    original = EvaluarCalidadTelemetriaUseCase._registrar_evidencia
    llamadas = []

    def fallar(self,*args,**kwargs):
        original(self,*args,**kwargs)
        llamadas.append(True)
        raise RuntimeError('fallo inducido despues de persistir la auditoria')

    with monkeypatch.context() as cambios:
        cambios.setattr(EvaluarCalidadTelemetriaUseCase,'_registrar_evidencia',fallar)
        with pytest.raises(RuntimeError,match='auditoria'):
            client.post(f'/iot/calidad/{identificador}/evaluar',headers=e['headers'])
    assert llamadas==[True]
    assert db_session.execute(text('SELECT count(*) FROM modulo3.telemetria_calidad WHERE id_telemetria=:id'),{'id':identificador}).scalar_one()==0
    assert fila(db_session,identificador)==antes
    r = client.post(f'/iot/calidad/{identificador}/evaluar',headers=e['headers'])
    assert r.status_code==201,r.text
    assert r.json()['apto_para_ia'] is False and r.json()['apto_para_nic41'] is False

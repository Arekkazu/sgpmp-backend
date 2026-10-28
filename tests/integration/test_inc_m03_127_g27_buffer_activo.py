# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-127-G27 RF-54/60: validar estabilidad HTTP/SQL, vaciado, historial, rollback y concurrencia bajo rol API. |
"""PostgreSQL real exclusivo; no se modifica el dispositivo oficial ni se ejecuta firmware."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
import importlib.util
from pathlib import Path
from threading import Event

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,event,text
from sqlalchemy.orm import Session

from src.shared import database as modulo_db,jwt as jwt_module
from src.shared.database import get_db,get_db_sistema
from src.shared.error_handlers import register_error_handlers
from src.telemetry.infrastructure.routers.infraestructura_iot_router import router
from src.telemetry.infrastructure.repositories.estado_dispositivo_iot_repository import SqlAlchemyEstadoDispositivoIoTRepository
from src.telemetry.infrastructure.repositories.alerta_repository import SqlAlchemyAlertaRepository
from src.telemetry.infrastructure.repositories.periodo_inactividad_repository import SqlAlchemyPeriodoInactividadRepository
from src.telemetry.infrastructure.adapters.parametros_heartbeat_mlops_adapter import ParametrosHeartbeatMLOpsAdapter
from src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case import EvaluarEstadoDispositivosUseCase
from src.telemetry.infrastructure.workers.postcommit_worker import construir_procesador

_spec=importlib.util.spec_from_file_location('g28_base',Path(__file__).with_name('test_dev27_heartbeat_parametros.py'))
p=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(p)
h=p.h
modelos=p.modelos
parametros_rf60=p.parametros_rf60
politica=p.politica
pytestmark=pytest.mark.integration


@pytest.fixture
def contexto(db_session,crear_usuario_db,crear_auth_headers,politica):
    equipo=h.hardware(db_session)
    finca=db_session.execute(text('SELECT id_finca FROM modulo9.infraestructuras WHERE id_infraestructura=:a'),{'a':equipo['area']}).scalar_one()
    rol=db_session.execute(text("SELECT id_rol FROM modulo1.roles WHERE nombre_rol='Ingeniero de Campo'")).scalar_one()
    ingeniero=crear_usuario_db(id_rol=rol)
    externo=crear_usuario_db(id_rol=rol)
    rol_denegado=db_session.execute(text('''SELECT r.id_rol FROM modulo1.roles r WHERE NOT EXISTS (
        SELECT 1 FROM modulo1.permisos p WHERE p.id_rol=r.id_rol AND p.id_recurso=35 AND p.id_accion=2 AND p.es_activo) LIMIT 1''')).scalar_one()
    denegado=crear_usuario_db(id_rol=rol_denegado)
    db_session.execute(text('''INSERT INTO modulo9.usuarios_fincas(id_usuario_finca,id_usuario,id_finca,es_activo)
        SELECT COALESCE(max(id_usuario_finca),0)+1,:u,:f,true FROM modulo9.usuarios_fincas
        ON CONFLICT(id_usuario,id_finca) DO NOTHING'''),{'u':ingeniero['id_usuario'],'f':finca})
    headers={n:crear_auth_headers(u) for n,u in [('ingeniero',ingeniero),('externo',externo),('denegado',denegado)]}
    db_session.commit()
    return equipo | {'headers':headers}


@pytest.fixture
def cliente(db_session,monkeypatch):
    monkeypatch.setattr(jwt_module,'_SECRET_KEY','sgpmp-integration-tests-only')
    monkeypatch.setattr(jwt_module,'_EXPIRE_HOURS',8)
    monkeypatch.setattr(modulo_db,'_id_usuario_servicio',None)
    monkeypatch.setenv('BROKER_SERVICE_TOKEN','g28-broker-test-only')
    app=FastAPI();register_error_handlers(app);app.include_router(router)
    def rol_api(s,t,c):c.exec_driver_sql('SET LOCAL ROLE sgpmp_app')
    def sesion(sistema=False):
        db_session.info.clear()
        event.listen(db_session,'after_begin',rol_api)
        db_session.execute(text('SET LOCAL ROLE sgpmp_app'))
        assert db_session.execute(text('SELECT current_user')).scalar_one()=='sgpmp_app'
        assert db_session.execute(text('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')).one()==(False,False)
        if sistema:modulo_db.declarar_identidad_sistema(db_session)
        try:yield db_session
        finally:
            event.remove(db_session,'after_begin',rol_api)
            db_session.execute(text('RESET ROLE'));db_session.info.clear()
    def lectura():yield from sesion()
    def sistema():yield from sesion(True)
    app.dependency_overrides[get_db]=lectura
    app.dependency_overrides[get_db_sistema]=sistema
    with TestClient(app,raise_server_exceptions=False) as c:yield c


def evaluar(db):
    return EvaluarEstadoDispositivosUseCase(db,SqlAlchemyEstadoDispositivoIoTRepository(db),None,
        SqlAlchemyPeriodoInactividadRepository(db),SqlAlchemyAlertaRepository(db),None,ParametrosHeartbeatMLOpsAdapter(db))


def bajo_rol_api(db,operacion):
    db.info.clear();db.execute(text('SET LOCAL ROLE sgpmp_app'));modulo_db.declarar_identidad_sistema(db)
    try:return operacion()
    finally:db.execute(text('RESET ROLE'));db.info.clear()


def enviar(cliente,ctx,buffer='A',pendientes=37):
    r=cliente.post('/iot/heartbeat',headers={'Authorization':'Bearer g28-broker-test-only'},json=dict(
        device_id=ctx['device'],serial=ctx['serial'],tipo_mensaje='HEARTBEAT',estado_local_buffer=buffer,
        datos_pendientes_buffer=pendientes,fecha_registro=datetime.now(timezone.utc).isoformat()))
    assert r.status_code==200,r.text
    return r.json()['id_heartbeat']


def insertar(db,ctx,buffer='A',pendientes=37,fecha=None):
    return db.execute(text('''INSERT INTO modulo3.heartbeats
        (id_dispositivo_iot,tipo_mensaje,estado_local_buffer,datos_pendientes_buffer,fecha_registro,fecha_recepcion)
        VALUES (:d,'HEARTBEAT',:b,:n,:f,:f) RETURNING id_heartbeat'''),
        {'d':ctx['device'],'b':buffer,'n':pendientes,'f':fecha or datetime.now(timezone.utc)}).scalar_one()


def estado(db,ctx):
    return db.execute(text('SELECT estado_actual::text FROM modulo3.estados_dispositivos_iot WHERE id_dispositivo_iot=:d'),{'d':ctx['device']}).scalar_one()


def historial(db,ctx):
    return db.execute(text('''SELECT estado_anterior::text,estado_nuevo::text FROM modulo3.historico_transiciones_dispositivos
        WHERE id_dispositivo_iot=:d ORDER BY id_transaccion'''),{'d':ctx['device']}).all()


@pytest.mark.parametrize('canal',['HTTP','SQL'])
def test_no_vuelve_a_activo_sin_mensaje_nuevo_y_vacia_con_nuevo_reporte(cliente,contexto,db_session,canal):
    enviar(cliente,contexto,'I',0)
    if canal=='HTTP':identificador=enviar(cliente,contexto)
    else:
        identificador=bajo_rol_api(db_session,lambda:insertar(db_session,contexto));db_session.commit()
    assert estado(db_session,contexto)=='BUFFER_ACTIVO'
    antes=historial(db_session,contexto)
    for _ in range(3):
        assert bajo_rol_api(db_session,lambda:evaluar(db_session).execute(contexto['device']))==0
        assert estado(db_session,contexto)=='BUFFER_ACTIVO'
    assert historial(db_session,contexto)==antes==[('ACTIVO','BUFFER_ACTIVO')]
    assert db_session.execute(text('SELECT count(*) FROM modulo3.heartbeats WHERE id_dispositivo_iot=:d'),{'d':contexto['device']}).scalar_one()==2
    assert db_session.execute(text('SELECT count(*) FROM modulo3.periodos_inactividad WHERE id_dispositivo_iot=:d AND fecha_fin IS NULL'),{'d':contexto['device']}).scalar_one()==1
    worker=construir_procesador(db_session.get_bind(),identidad=True)
    bajo_rol_api(db_session,worker.execute)
    bajo_rol_api(db_session,worker.execute)
    assert estado(db_session,contexto)=='BUFFER_ACTIVO' and historial(db_session,contexto)==antes
    assert db_session.execute(text("SELECT count(*) FROM modulo3.bitacora_auditoria_iot WHERE tipo_evento='POSTCOMMIT_HEARTBEAT_ESTADO_COMPLETADO' AND entidad_afectada_id=:h"),{'h':str(identificador)}).scalar_one()==1
    enviar(cliente,contexto,'I',0)
    assert estado(db_session,contexto)=='ACTIVO'
    assert historial(db_session,contexto)==antes+[('BUFFER_ACTIVO','ACTIVO')]
    assert db_session.execute(text('SELECT count(*) FROM modulo3.periodos_inactividad WHERE id_dispositivo_iot=:d AND fecha_fin IS NULL'),{'d':contexto['device']}).scalar_one()==0


def test_heartbeat_repetido_y_lleno_no_generan_oscilaciones(cliente,contexto,db_session):
    enviar(cliente,contexto,'I',0)
    for buffer in ['A','A','L']:
        enviar(cliente,contexto,buffer,37)
        assert estado(db_session,contexto)=='BUFFER_ACTIVO'
    assert historial(db_session,contexto)==[('ACTIVO','BUFFER_ACTIVO')]
    assert db_session.execute(text('SELECT count(*) FROM modulo3.periodos_inactividad WHERE id_dispositivo_iot=:d AND fecha_fin IS NULL'),{'d':contexto['device']}).scalar_one()==1


def test_procedimiento_legacy_respeta_pendientes_y_no_repite_historial(cliente,contexto,db_session):
    enviar(cliente,contexto,'I',0);enviar(cliente,contexto)
    for _ in range(2):bajo_rol_api(db_session,lambda:db_session.execute(text('CALL modulo3.sp_clasificar_estado_dispositivo(:d)'),{'d':contexto['device']}))
    db_session.commit()
    assert estado(db_session,contexto)=='BUFFER_ACTIVO'
    assert historial(db_session,contexto)==[('ACTIVO','BUFFER_ACTIVO')]


def test_reporte_anterior_no_sustituye_vaciado_mas_reciente(cliente,contexto,db_session):
    ultimo=enviar(cliente,contexto,'I',0)
    bajo_rol_api(db_session,lambda:insertar(db_session,contexto,fecha=datetime.now(timezone.utc)-timedelta(hours=1)))
    db_session.commit()
    assert estado(db_session,contexto)=='ACTIVO'
    assert db_session.execute(text('SELECT id_ultimo_heardbeat FROM modulo3.estados_dispositivos_iot WHERE id_dispositivo_iot=:d'),{'d':contexto['device']}).scalar_one()==ultimo
    assert bajo_rol_api(db_session,lambda:evaluar(db_session).execute(contexto['device']))==0


def test_mantenimiento_no_es_sobrescrito(cliente,contexto,db_session):
    enviar(cliente,contexto,'I',0)
    db_session.execute(text("UPDATE modulo3.estados_dispositivos_iot SET estado_actual='EN_MANTENIMIENTO' WHERE id_dispositivo_iot=:d"),{'d':contexto['device']});db_session.commit()
    enviar(cliente,contexto)
    assert bajo_rol_api(db_session,lambda:evaluar(db_session).execute(contexto['device']))==0
    assert estado(db_session,contexto)=='EN_MANTENIMIENTO'


def test_api_estado_conserva_jwt_rbac_y_aislamiento(cliente,contexto):
    enviar(cliente,contexto)
    ruta='/iot/dispositivos/'+str(contexto['device'])+'/estado'
    r=cliente.get(ruta,headers=contexto['headers']['ingeniero'])
    assert r.status_code==200,r.text
    assert r.json()['estado']['estado_actual']=='BUFFER_ACTIVO'
    assert cliente.get(ruta).status_code==401
    assert cliente.get(ruta,headers=contexto['headers']['denegado']).status_code==403
    assert cliente.get(ruta,headers=contexto['headers']['externo']).status_code==404


def test_rollback_revierte_estado_heartbeat_historial_y_periodo(cliente,contexto,db_session):
    enviar(cliente,contexto,'I',0)
    bajo_rol_api(db_session,lambda:insertar(db_session,contexto))
    assert estado(db_session,contexto)=='BUFFER_ACTIVO'
    db_session.rollback()
    assert estado(db_session,contexto)=='ACTIVO'
    assert historial(db_session,contexto)==[]
    assert db_session.execute(text('SELECT count(*) FROM modulo3.periodos_inactividad WHERE id_dispositivo_iot=:d'),{'d':contexto['device']}).scalar_one()==0


@pytest.fixture
def motor_api(integration_engine,monkeypatch):
    assert (integration_engine.url.host,integration_engine.url.port,integration_engine.url.database)==('127.0.0.1',55427,'sgpmp_g28_test')
    monkeypatch.setattr(modulo_db,'_id_usuario_servicio',None)
    motor=create_engine(integration_engine.url,use_insertmanyvalues=False,connect_args={'options':'-c role=sgpmp_app'})
    try:yield motor
    finally:motor.dispose()


def test_heartbeats_concurrentes_no_intercalan_activo(integration_engine,motor_api):
    with Session(integration_engine) as db:
        ctx=h.hardware(db);insertar(db,ctx,'I',0);db.commit()
    def reportar(buffer):
        with Session(motor_api) as db:
            modulo_db.declarar_identidad_sistema(db)
            insertar(db,ctx,buffer,37);db.commit()
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(reportar,['A','L']))
    with Session(integration_engine) as db:
        assert estado(db,ctx)=='BUFFER_ACTIVO'
        assert historial(db,ctx)==[('ACTIVO','BUFFER_ACTIVO')]


def test_bloqueo_serializa_vaciado_con_evaluacion(integration_engine,motor_api):
    with Session(integration_engine) as db:
        ctx=h.hardware(db);insertar(db,ctx,'I',0);insertar(db,ctx);db.commit()
    bloqueado,continuar,intento,termino=Event(),Event(),Event(),Event()
    def lectura():
        with Session(motor_api) as db:
            modulo_db.declarar_identidad_sistema(db)
            SqlAlchemyEstadoDispositivoIoTRepository(db).bloquear_por_dispositivo(ctx['device'])
            bloqueado.set()
            assert continuar.wait(10)
            db.execute(text('CALL modulo3.sp_clasificar_estado_dispositivo(:d)'),{'d':ctx['device']})
            db.commit()
    def vaciar():
        assert bloqueado.wait(10)
        with Session(motor_api) as db:
            modulo_db.declarar_identidad_sistema(db);intento.set()
            insertar(db,ctx,'I',0);db.commit();termino.set()
    with ThreadPoolExecutor(max_workers=2) as pool:
        lector=pool.submit(lectura);escritor=pool.submit(vaciar)
        try:
            assert intento.wait(10)
            assert not termino.wait(.15)
        finally:continuar.set()
        lector.result(timeout=10);escritor.result(timeout=10)
    with Session(integration_engine) as db:
        assert estado(db,ctx)=='ACTIVO'
        assert historial(db,ctx)==[('ACTIVO','BUFFER_ACTIVO'),('BUFFER_ACTIVO','ACTIVO')]


def test_migracion_reversible_sin_cambiar_politicas_ni_permisos(integration_engine,monkeypatch):
    from alembic import command
    from alembic.config import Config
    url=integration_engine.url
    if (url.host,url.port,url.database)!=('127.0.0.1',55427,'sgpmp_g28_test'):
        pytest.skip('El downgrade se permite solo en sgpmp_g28_test local exclusiva.')
    archivo=Path(__file__).resolve().parents[2]/'alembic/versions/c68227f60a01_rf60_conservar_buffer_activo.py'
    spec=importlib.util.spec_from_file_location('g28_migracion',archivo)
    migracion=importlib.util.module_from_spec(spec);spec.loader.exec_module(migracion)
    def definiciones():
        with integration_engine.connect() as db:
            return {n:d for n,d in db.execute(text("SELECT proname,pg_get_functiondef(oid) FROM pg_proc WHERE oid IN ('modulo3.fn_procesar_heartbeat()'::regprocedure,'modulo3.sp_clasificar_estado_dispositivo(integer,integer,integer)'::regprocedure)"))}
    def politicas():
        with integration_engine.connect() as db:
            return db.execute(text("SELECT tablename,policyname,qual,with_check FROM pg_policies WHERE schemaname IN ('modulo3','modulo9') ORDER BY tablename,policyname")).all()
    anteriores=politicas()
    monkeypatch.setenv('ALEMBIC_DATABASE_URL',url.render_as_string(hide_password=False))
    config=Config(str(archivo.parents[2]/'alembic.ini'))
    try:
        command.downgrade(config,'ebbb160365e5')
        defs=definiciones()
        assert defs['fn_procesar_heartbeat'].split()==migracion._HEARTBEAT_ANTERIOR.split()
        assert defs['sp_clasificar_estado_dispositivo'].split()==migracion._CLASIFICAR_ANTERIOR.split()
    finally:command.upgrade(config,'head')
    assert politicas()==anteriores
    with integration_engine.connect() as db:
        assert db.execute(text('SELECT version_num FROM alembic_version')).scalar_one()=='c68227f60a01'
        assert db.execute(text("SELECT rolbypassrls,rolsuper FROM pg_roles WHERE rolname='sgpmp_app'")).one()==(False,False)

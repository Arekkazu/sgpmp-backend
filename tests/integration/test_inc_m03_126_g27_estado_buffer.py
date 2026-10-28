# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-126-G27 RF-54: validar HTTP, inserción directa del broker, migración, JWT, RBAC y RLS con PostgreSQL real. |
# | 2026-10-28 | Arekkazu | INC-M03-126-G27 RF-54: no fija el head de Alembic (la columna ya prueba la migracion) |
"""Sin firmware ni broker MQTT real; se ejercita su INSERT en una base local exclusiva."""
from datetime import datetime,timedelta,timezone
from decimal import Decimal
import importlib.util
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text,event

from src.shared import database as modulo_db,jwt as jwt_module
from src.shared.database import get_db,get_db_sistema
from src.shared.error_handlers import register_error_handlers
from src.telemetry.infrastructure.routers.infraestructura_iot_router import router

_spec=importlib.util.spec_from_file_location('g27_base',Path(__file__).with_name('test_dev05_ingesta_bplus_postcommit.py'))
h=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(h)
modelos=h.modelos
pytestmark=pytest.mark.integration


@pytest.fixture
def contexto(db_session,crear_usuario_db,crear_auth_headers):
    equipo=h.hardware(db_session)
    finca=db_session.execute(text('SELECT id_finca FROM modulo9.infraestructuras WHERE id_infraestructura=:a'),{'a':equipo['area']}).scalar_one()
    roles=db_session.execute(text('''SELECT r.id_rol,r.nombre_rol,r.es_protegido,EXISTS(
        SELECT 1 FROM modulo1.permisos p WHERE p.id_rol=r.id_rol AND p.id_recurso=35 AND p.id_accion=2 AND p.es_activo) AS puede
        FROM modulo1.roles r ORDER BY r.id_rol''')).mappings().all()
    admin=crear_usuario_db(id_rol=next(r['id_rol'] for r in roles if r['es_protegido']))
    ingeniero=crear_usuario_db(id_rol=next(r['id_rol'] for r in roles if r['puede'] and r['nombre_rol']=='Ingeniero de Campo'))
    externo=crear_usuario_db(id_rol=ingeniero['id_rol'])
    sin_permiso=crear_usuario_db(id_rol=next(r['id_rol'] for r in roles if not r['puede']))
    db_session.execute(text('''INSERT INTO modulo9.usuarios_fincas(id_usuario_finca,id_usuario,id_finca,es_activo)
        SELECT COALESCE(max(id_usuario_finca),0)+1,:u,:f,true FROM modulo9.usuarios_fincas
        ON CONFLICT (id_usuario,id_finca) DO NOTHING'''),{'u':ingeniero['id_usuario'],'f':finca})
    headers={nombre:crear_auth_headers(usuario) for nombre,usuario in
             [('admin',admin),('ingeniero',ingeniero),('externo',externo),('sin_permiso',sin_permiso)]}
    db_session.commit()
    return equipo | {'headers':headers,'ingeniero':ingeniero,'finca':finca}


@pytest.fixture
def cliente(db_session,monkeypatch):
    monkeypatch.setattr(jwt_module,'_SECRET_KEY','sgpmp-integration-tests-only')
    monkeypatch.setattr(jwt_module,'_EXPIRE_HOURS',8)
    monkeypatch.setenv('BROKER_SERVICE_TOKEN','g27-broker-test-only')
    monkeypatch.setattr(modulo_db,'_id_usuario_servicio',None)
    app=FastAPI();register_error_handlers(app);app.include_router(router)
    def rol_api(s,t,c):
        c.exec_driver_sql('SET LOCAL ROLE sgpmp_app')
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
            db_session.execute(text('RESET ROLE'))
            db_session.info.clear()
    def lectura():yield from sesion()
    def sistema():yield from sesion(True)
    app.dependency_overrides[get_db]=lectura
    app.dependency_overrides[get_db_sistema]=sistema
    with TestClient(app,raise_server_exceptions=False) as c:yield c


def body(ctx,usada=800,metricas=True,**cambios):
    ahora=datetime.now(timezone.utc)-timedelta(seconds=2)
    datos=dict(device_id=ctx['device'],serial=ctx['serial'],tipo_mensaje='HEARTBEAT',
        fecha_registro=ahora.isoformat(),estado_local_buffer='A',datos_pendientes_buffer=7)
    if metricas:
        datos['metricas_buffer']=dict(capacidad_total=1000,capacidad_utilizada=usada,
            ultimo_timestamp_pendiente=(ahora-timedelta(seconds=5)).isoformat(),
            politica_buffer_activa='POLITICA_RECHAZO')
    return datos | cambios


def enviar(cliente,ctx,**kwargs):
    r=cliente.post('/iot/heartbeat',json=body(ctx,**kwargs),headers={'Authorization':'Bearer g27-broker-test-only'})
    assert r.status_code==200,r.text
    return r.json()['id_heartbeat']


def consultar(cliente,ctx,rol='ingeniero'):
    return cliente.get('/iot/dispositivos/'+str(ctx['device'])+'/buffer',headers=ctx['headers'][rol])


def test_transiciones_normal_warning_critico_y_recuperacion(cliente,contexto,db_session):
    for usada,estado in [(799,'NORMAL'),(800,'WARNING'),(949,'WARNING'),(950,'CRITICO'),(1000,'CRITICO'),(300,'NORMAL')]:
        identificador=enviar(cliente,contexto,usada=usada)
        r=consultar(cliente,contexto)
        assert r.status_code==200,r.text
        d=r.json()
        assert d['id_heartbeat']==identificador and d['estado_buffer']==estado
        assert Decimal(d['porcentaje_ocupacion'])==Decimal(usada)/10
        assert d['datos_pendientes']==7 and d['politica_buffer_activa']=='POLITICA_RECHAZO'
        guardado=db_session.execute(text('SELECT json_metricas_buffer FROM modulo3.heartbeats WHERE id_heartbeat=:h'),{'h':identificador}).scalar_one()
        assert Decimal(guardado['capacidad_utilizada'])==usada
        assert datetime.fromisoformat(d['ultimo_timestamp_pendiente'])==datetime.fromisoformat(guardado['ultimo_timestamp_pendiente'])


def test_dispositivo_sin_heartbeat_no_simula_buffer_vacio(cliente,contexto):
    r=consultar(cliente,contexto)
    assert r.status_code==200,r.text
    d=r.json()
    assert d['datos_pendientes'] is d['estado_buffer'] is d['id_heartbeat'] is None
    assert not d['metricas_disponibles']


def test_heartbeat_legacy_posterior_no_mezcla_snapshot_anterior(cliente,contexto):
    enviar(cliente,contexto,usada=950)
    identificador=enviar(cliente,contexto,metricas=False,datos_pendientes_buffer=2)
    r=consultar(cliente,contexto)
    assert r.status_code==200,r.text
    d=r.json()
    assert d['id_heartbeat']==identificador and d['datos_pendientes']==2
    assert d['estado_buffer'] is d['capacidad_total'] is d['ultimo_timestamp_pendiente'] is None
    assert not d['metricas_disponibles']


def test_insert_directo_del_broker_es_observable_sin_pasar_por_dto(cliente,contexto,db_session):
    datos=body(contexto,usada=995)
    snapshot=datos['metricas_buffer'] | {'politica_buffer_activa':'POLITICA_SOBRESCRITURA'}
    identificador=db_session.execute(text('''INSERT INTO modulo3.heartbeats
        (id_dispositivo_iot,tipo_mensaje,datos_pendientes_buffer,estado_local_buffer,fecha_registro,fecha_recepcion,json_metricas_buffer)
        VALUES (:id,'HEARTBEAT',7,'L',now(),now(),CAST(:m AS jsonb)) RETURNING id_heartbeat'''),
        {'id':contexto['device'],'m':json.dumps(snapshot)}).scalar_one()
    db_session.commit()
    r=consultar(cliente,contexto,'admin')
    assert r.status_code==200,r.text
    assert r.json()['id_heartbeat']==identificador and r.json()['estado_buffer']=='CRITICO'
    assert r.json()['politica_buffer_activa']=='POLITICA_SOBRESCRITURA'


def test_rbac_y_aislamiento_de_finca_con_jwt_real(cliente,contexto):
    enviar(cliente,contexto)
    assert consultar(cliente,contexto,'admin').status_code==200
    assert consultar(cliente,contexto,'sin_permiso').status_code==403
    assert consultar(cliente,contexto,'externo').status_code==404
    assert cliente.get('/iot/dispositivos/'+str(contexto['device'])+'/buffer').status_code==401
    assert cliente.get('/iot/dispositivos/'+str(contexto['device'])+'/buffer',headers={'Authorization':'Bearer inventado'}).status_code==401


def test_reporte_invalido_se_rechaza_sin_escribir(cliente,contexto,db_session):
    dato=body(contexto);dato['metricas_buffer']['capacidad_utilizada']=1001
    r=cliente.post('/iot/heartbeat',json=dato,headers={'Authorization':'Bearer g27-broker-test-only'})
    assert r.status_code==400,r.text
    assert db_session.execute(text('SELECT count(*) FROM modulo3.heartbeats WHERE id_dispositivo_iot=:d'),{'d':contexto['device']}).scalar_one()==0


def test_empate_de_recepcion_se_resuelve_por_id(cliente,contexto,db_session):
    fecha=datetime.now(timezone.utc)
    ids=[]
    for usada in [950,200]:
        ids.append(db_session.execute(text('''INSERT INTO modulo3.heartbeats
            (id_dispositivo_iot,tipo_mensaje,datos_pendientes_buffer,fecha_registro,fecha_recepcion,json_metricas_buffer)
            VALUES (:id,'HEARTBEAT',7,:f,:f,CAST(:m AS jsonb)) RETURNING id_heartbeat'''),
            {'id':contexto['device'],'f':fecha,'m':json.dumps(body(contexto,usada=usada)['metricas_buffer'])}).scalar_one())
    db_session.commit()
    r=consultar(cliente,contexto)
    assert r.status_code==200,r.text
    assert r.json()['id_heartbeat']==ids[1] and r.json()['estado_buffer']=='NORMAL'


def test_fallo_commit_revierte_snapshot_y_heartbeat(cliente,contexto,db_session,monkeypatch):
    def fallar():raise RuntimeError('fallo de commit de prueba')
    with monkeypatch.context() as cambios:
        cambios.setattr(db_session,'commit',fallar)
        r=cliente.post('/iot/heartbeat',json=body(contexto),headers={'Authorization':'Bearer g27-broker-test-only'})
    assert r.status_code==500,r.text
    assert db_session.execute(text('SELECT count(*) FROM modulo3.heartbeats WHERE id_dispositivo_iot=:d'),{'d':contexto['device']}).scalar_one()==0


def test_migracion_nullable_sin_tabla_buffers_y_politicas_preservadas(integration_engine):
    with integration_engine.connect() as db:
        assert db.execute(text("SELECT is_nullable,data_type FROM information_schema.columns WHERE table_schema='modulo3' AND table_name='heartbeats' AND column_name='json_metricas_buffer'")).one()==('YES','jsonb')
        assert db.execute(text("SELECT to_regclass('modulo3.buffers')")).scalar_one() is None
        assert db.execute(text("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='modulo9.dispositivos_iot'::regclass")).one()==(True,True)


def test_buffer_vacio_reportado_se_distingue_de_ausencia_de_datos(cliente,contexto):
    snapshot=body(contexto,usada=0)['metricas_buffer'] | {'ultimo_timestamp_pendiente':None}
    enviar(cliente,contexto,usada=0,datos_pendientes_buffer=0,estado_local_buffer='I',metricas_buffer=snapshot)
    r=consultar(cliente,contexto)
    assert r.status_code==200,r.text
    d=r.json()
    assert d['metricas_disponibles'] and d['estado_buffer']=='NORMAL'
    assert Decimal(d['porcentaje_ocupacion'])==0 and d['datos_pendientes']==0
    assert d['ultimo_timestamp_pendiente'] is None


def test_upgrade_downgrade_preserva_heartbeat_legacy(integration_engine,monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy.orm import Session
    url=integration_engine.url
    if (url.host,url.port,url.database)!=('127.0.0.1',55427,'sgpmp_g27_test'):
        pytest.skip('La prueba de downgrade exige exclusivamente la base local sgpmp_g27_test.')
    with Session(integration_engine) as db:
        equipo=h.hardware(db)
        identificador=db.execute(text('''INSERT INTO modulo3.heartbeats
            (id_dispositivo_iot,tipo_mensaje,datos_pendientes_buffer,fecha_registro,fecha_recepcion)
            VALUES (:d,'HEARTBEAT',3,now(),now()) RETURNING id_heartbeat'''),{'d':equipo['device']}).scalar_one()
        db.commit()
    monkeypatch.setenv('ALEMBIC_DATABASE_URL',url.render_as_string(hide_password=False))
    config=Config(str(Path(__file__).resolve().parents[2]/'alembic.ini'))
    try:
        command.downgrade(config,'ebbb160365e5')
        with integration_engine.connect() as db:
            assert not db.execute(text("SELECT 1 FROM information_schema.columns WHERE table_schema='modulo3' AND table_name='heartbeats' AND column_name='json_metricas_buffer'")).scalar()
            assert db.execute(text('SELECT datos_pendientes_buffer FROM modulo3.heartbeats WHERE id_heartbeat=:h'),{'h':identificador}).scalar_one()==3
    finally:
        command.upgrade(config,'head')
    with integration_engine.connect() as db:
        assert db.execute(text('SELECT datos_pendientes_buffer,json_metricas_buffer FROM modulo3.heartbeats WHERE id_heartbeat=:h'),{'h':identificador}).one()==(3,None)

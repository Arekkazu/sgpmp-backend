# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-42 RF-60: verifica flujos HTTP y SQL postcommit en PostgreSQL |
# | 2026-10-29 | Arekkazu | INC-M03-134-G03 RF-60/RF-53: mantenimiento desde cualquier estado |
"""SQL directo representa la frontera del broker; no es MQTT extremo a extremo."""
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import os
import subprocess
import sys
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.telemetry.infrastructure.routers import infraestructura_iot_router
from src.telemetry.infrastructure.workers.postcommit_worker import construir_procesador

_spec = importlib.util.spec_from_file_location('dev42_base',Path(__file__).with_name('test_dev27_heartbeat_parametros.py'))
h = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h)
modelos, equipo, client, parametros_rf60, politica = h.modelos,h.equipo,h.client,h.parametros_rf60,h.politica
parametros_rf62 = h.h.parametros_rf62
pytestmark = pytest.mark.integration


def alertas(db,equipo):
    return db.execute(text('''SELECT id_alerta,tipo_variable,severidad,estado_alerta,metadato_evento
        FROM modulo3.alertas WHERE id_dispositivo_ioit=:id ORDER BY id_alerta'''),{'id':equipo['device']}).mappings().all()


def body(equipo,**cambios):
    return dict(dict(device_id=equipo['device'],serial=equipo['serial'],tipo_mensaje='HEARTBEAT',
        fecha_registro=datetime.now(timezone.utc).isoformat(),estado_local_buffer='I'),**cambios)


@pytest.mark.parametrize('canal',['HTTP','SQL'])
def test_e2_reloj_futuro_no_adelanta_contacto_y_no_duplica(client,db_session,equipo,politica,canal):
    futuro = datetime.now(timezone.utc)+timedelta(hours=3)
    if canal=='HTTP':
        r = client.post('/iot/heartbeat',json=body(equipo,fecha_registro=futuro.isoformat(),reloj_sincronizado=True))
        assert r.status_code==200,r.text
    else:
        db_session.execute(text('''INSERT INTO modulo3.heartbeats
            (id_dispositivo_iot,tipo_mensaje,fecha_registro,fecha_recepcion,reloj_sincronizado)
            VALUES (:id,'HEARTBEAT',:futuro,clock_timestamp(),true)'''),{'id':equipo['device'],'futuro':futuro})
        db_session.commit()
    contacto = db_session.execute(text('SELECT fecha_ultimo_contacto FROM modulo3.estados_dispositivos_iot WHERE id_dispositivo_iot=:id'),{'id':equipo['device']}).scalar_one()
    assert contacto < datetime.now(timezone.utc)+timedelta(seconds=2)
    assert db_session.execute(text('SELECT reloj_sincronizado FROM modulo3.heartbeats WHERE id_dispositivo_iot=:id'),{'id':equipo['device']}).scalar_one() is False
    w = construir_procesador(db_session.get_bind(),identidad=False)
    w.execute(); w.execute()
    filas=alertas(db_session,equipo)
    assert len(filas)==1 and filas[0]['tipo_variable']=='DESINCRONIZACION_RELOJ'
    assert filas[0]['metadato_evento']['reloj_desincronizado'] is True


@pytest.mark.parametrize('canal',['HTTP','SQL'])
def test_e4_bateria_es_una_alerta_escalada_sin_nuevos_historiales(client,db_session,equipo,politica,canal):
    w = construir_procesador(db_session.get_bind(),identidad=False)
    for bateria,causa in [(20,'BATERIA_BAJA'),(8,'BATERIA_CRITICA'),(5,'APAGADO_INMINENTE'),(5,'APAGADO_INMINENTE'),(25,'APAGADO_INMINENTE')]:
        if canal=='HTTP':
            r=client.post('/iot/heartbeat',json=body(equipo,nivel_bateria_pct=bateria))
            assert r.status_code==200,r.text
        else:
            h.h.guardar_heartbeat(db_session,equipo,bateria=bateria,buffer='I')
        w.execute();w.execute()
        filas=alertas(db_session,equipo)
        assert len(filas)==1
        assert (filas[0]['metadato_evento'] or {}).get('condicion_bateria',filas[0]['tipo_variable'])==causa
    assert filas[0]['severidad']=='CRITICO'
    assert db_session.execute(text('SELECT count(*) FROM modulo3.historico_estados_alertas WHERE id_alerta=:id'),{'id':filas[0]['id_alerta']}).scalar_one()==1


@pytest.mark.parametrize('buffer,esperado',[('A','BUFFER_ACTIVO'),('I','SIN_SEÑAL'),(None,'SIN_SEÑAL')])
def test_e5_periodico_usa_buffer_real_y_no_infiere_buffer_ausente(db_session,equipo,politica,buffer,esperado):
    h.h.guardar_heartbeat(db_session,equipo,buffer=buffer,fecha=datetime.now(timezone.utc)-timedelta(minutes=20))
    h.evaluador(db_session).execute();h.evaluador(db_session).execute()
    assert db_session.execute(text('SELECT estado_actual FROM modulo3.estados_dispositivos_iot WHERE id_dispositivo_iot=:id'),{'id':equipo['device']}).scalar_one()==esperado
    if buffer=='A':
        assert not alertas(db_session,equipo)


def perder_contacto(db,equipo):
    db.execute(text("UPDATE modulo3.estados_dispositivos_iot SET fecha_ultimo_contacto=clock_timestamp()-interval '20 minutes' WHERE id_dispositivo_iot=:id"),{'id':equipo['device']})
    db.commit()
    h.evaluador(db).execute()


@pytest.mark.parametrize('recuperacion',['HTTP','SQL','TELEMETRIA'])
def test_e6_cierra_solo_conectividad_sin_historia_duplicada(client,db_session,equipo,politica,parametros_rf62,recuperacion):
    h.h.guardar_heartbeat(db_session,equipo,bateria=20,buffer='I')
    w=construir_procesador(db_session.get_bind(),identidad=False)
    w.execute()
    perder_contacto(db_session,equipo)
    if recuperacion=='HTTP':
        assert client.post('/iot/heartbeat',json=body(equipo)).status_code==200
    elif recuperacion=='SQL':
        h.h.guardar_heartbeat(db_session,equipo,buffer='I')
    else:
        h.h.calibrar(db_session,equipo)
        h.h.sql_ingesta(db_session,equipo)
    w.execute();w.execute()
    estados={a['tipo_variable']:a['estado_alerta'] for a in alertas(db_session,equipo)}
    assert estados['DISPOSITIVO_SIN_SEÑAL']=='RESUELTA'
    assert estados['BATERIA_BAJA']=='ACTIVA'
    cambios=db_session.execute(text('''SELECT estado_anterior,estado_nuevo,count(*)
        FROM modulo3.historico_transiciones_dispositivos WHERE id_dispositivo_iot=:id
        GROUP BY estado_anterior,estado_nuevo'''),{'id':equipo['device']}).all()
    assert ('SIN_SEÑAL','ACTIVO',1) in cambios
    assert db_session.execute(text('SELECT count(*) FROM modulo3.periodos_inactividad WHERE id_dispositivo_iot=:id AND fecha_fin IS NULL'),{'id':equipo['device']}).scalar_one()==0


def test_e10_telemetria_reciente_sin_heartbeat_activo_y_alerta_leve(client,db_session,equipo,politica,parametros_rf62):
    h.h.guardar_heartbeat(db_session,equipo,buffer='I',fecha=datetime.now(timezone.utc)-timedelta(minutes=10))
    h.h.calibrar(db_session,equipo)
    h.h.sql_ingesta(db_session,equipo)
    w=construir_procesador(db_session.get_bind(),identidad=False)
    w.execute();w.execute();h.evaluador(db_session).execute()
    filas=alertas(db_session,equipo)
    assert [(a['tipo_variable'],a['severidad']) for a in filas]==[('HEARTBEAT_AUSENTE','LEVE')]
    assert db_session.execute(text('SELECT estado_actual FROM modulo3.estados_dispositivos_iot WHERE id_dispositivo_iot=:id'),{'id':equipo['device']}).scalar_one()=='ACTIVO'
    assert client.post('/iot/heartbeat',json=body(equipo)).status_code==200
    w.execute();h.evaluador(db_session).execute()
    filas=alertas(db_session,equipo)
    assert len(filas)==1 and filas[0]['estado_alerta']=='RESUELTA'


@pytest.fixture
def cliente_manual(db_session,monkeypatch):
    import src.shared.jwt as jwt
    monkeypatch.setattr(jwt,'_SECRET_KEY','sgpmp-integration-tests-only')
    app=FastAPI();register_error_handlers(app);app.include_router(infraestructura_iot_router.router)
    app.dependency_overrides[get_db]=lambda:db_session
    with TestClient(app,raise_server_exceptions=False) as c:
        yield c


@pytest.mark.parametrize('origen,destino,http',[('INACTIVO','EN_MANTENIMIENTO',200),
    ('EN_MANTENIMIENTO','ACTIVO',200),('ACTIVO','EN_MANTENIMIENTO',200),
    ('INACTIVO','ACTIVO',422),('SIN_SEÑAL','ACTIVO',422),('EN_MANTENIMIENTO','INACTIVO',400)])
def test_fase5_http_respeta_transicion_historia_actor(cliente_manual,db_session,equipo,crear_usuario_db,crear_auth_headers,origen,destino,http):
    rol=db_session.execute(text('SELECT id_rol FROM modulo1.roles WHERE es_protegido')).scalar_one()
    usuario=crear_usuario_db(id_rol=rol)
    h.h.guardar_heartbeat(db_session,equipo,buffer='I')
    db_session.execute(text("UPDATE modulo3.estados_dispositivos_iot SET estado_actual=CAST(:estado AS modulo3.enum_estado_dispositivo), causa_primaria='FALLO_CONECTIVIDAD' WHERE id_dispositivo_iot=:id"),{'estado':origen,'id':equipo['device']});db_session.commit()
    antes=db_session.execute(text('SELECT count(*) FROM modulo3.historico_transiciones_dispositivos WHERE id_dispositivo_iot=:id'),{'id':equipo['device']}).scalar_one()
    r=cliente_manual.patch(f"/iot/dispositivos/{equipo['device']}/mantenimiento",headers=crear_auth_headers(usuario),json={'nuevo_estado':destino,'motivo':'Intervencion de prueba'})
    assert r.status_code==http,r.text
    despues=db_session.execute(text('SELECT count(*) FROM modulo3.historico_transiciones_dispositivos WHERE id_dispositivo_iot=:id'),{'id':equipo['device']}).scalar_one()
    assert despues==antes+(http==200)
    if http==422:
        assert r.json()['error_code']=='TRANSICION_INVALIDA'
    if http==200:
        actor=db_session.execute(text('''SELECT id_usuairo_responsable FROM modulo3.historico_transiciones_dispositivos
            WHERE id_dispositivo_iot=:id ORDER BY fecha_transicion DESC,id_transaccion DESC LIMIT 1'''),{'id':equipo['device']}).scalar_one()
        assert actor==usuario['id_usuario']
        detalle=db_session.execute(text("SELECT accion_detallada FROM modulo3.bitacora_auditoria_iot WHERE tipo_evento='TRANSICION_MANTENIMIENTO_MANUAL' AND entidad_afectada_id=:id"),{'id':str(equipo['device'])}).scalar_one()
        assert detalle['motivo']=='Intervencion de prueba'


def test_mantenimiento_sin_permiso_es_403_sin_cambios(cliente_manual,db_session,equipo,crear_usuario_db,crear_auth_headers):
    rol=db_session.execute(text('''SELECT r.id_rol FROM modulo1.roles r
        WHERE NOT EXISTS (SELECT 1 FROM modulo1.permisos p WHERE p.id_rol=r.id_rol
            AND p.id_recurso=35 AND p.id_accion=3 AND p.es_activo) LIMIT 1''')).scalar_one()
    usuario=crear_usuario_db(id_rol=rol)
    h.h.guardar_heartbeat(db_session,equipo,buffer='I')
    r=cliente_manual.patch(f"/iot/dispositivos/{equipo['device']}/mantenimiento",
        headers=crear_auth_headers(usuario),json={'nuevo_estado':'EN_MANTENIMIENTO'})
    assert r.status_code==403,r.text
    assert db_session.execute(text('SELECT count(*) FROM modulo3.historico_transiciones_dispositivos WHERE id_dispositivo_iot=:id'),{'id':equipo['device']}).scalar_one()==0


def test_mantenimiento_fuera_de_finca_es_404(cliente_manual,db_session,equipo,crear_usuario_db,crear_auth_headers):
    rol=db_session.execute(text('''SELECT r.id_rol FROM modulo1.roles r JOIN modulo1.permisos p USING(id_rol)
        WHERE NOT r.es_protegido AND p.id_recurso=35 AND p.id_accion=3 AND p.es_activo LIMIT 1''')).scalar_one()
    usuario=crear_usuario_db(id_rol=rol)
    h.h.guardar_heartbeat(db_session,equipo,buffer='I')
    r=cliente_manual.patch(f"/iot/dispositivos/{equipo['device']}/mantenimiento",
        headers=crear_auth_headers(usuario),json={'nuevo_estado':'EN_MANTENIMIENTO'})
    assert r.status_code==404,r.text


def test_mantenimiento_sin_sesion_es_401(cliente_manual,equipo):
    assert cliente_manual.patch(f"/iot/dispositivos/{equipo['device']}/mantenimiento",
        json={'nuevo_estado':'EN_MANTENIMIENTO'}).status_code==401


def test_fallo_de_resolucion_revierte_alertas_pero_conserva_heartbeat(client,db_session,equipo,politica,monkeypatch):
    from src.telemetry.infrastructure.repositories.alerta_repository import SqlAlchemyAlertaRepository
    h.h.guardar_heartbeat(db_session,equipo,buffer='I')
    perder_contacto(db_session,equipo)
    r=client.post('/iot/heartbeat',json=body(equipo))
    assert r.status_code==200
    cantidad=db_session.execute(text('SELECT count(*) FROM modulo3.heartbeats WHERE id_dispositivo_iot=:id'),{'id':equipo['device']}).scalar_one()
    original=SqlAlchemyAlertaRepository.actualizar_estado
    def fallar(self,identificador,destino,*args,**kwargs):
        if destino=='RESUELTA':
            raise RuntimeError('fallo transitorio de prueba')
        return original(self,identificador,destino,*args,**kwargs)
    monkeypatch.setattr(SqlAlchemyAlertaRepository,'actualizar_estado',fallar)
    w=construir_procesador(db_session.get_bind(),identidad=False,reintento_seg=1)
    w.execute()
    assert alertas(db_session,equipo)[0]['estado_alerta']=='ACTIVA'
    assert db_session.execute(text('SELECT count(*) FROM modulo3.heartbeats WHERE id_dispositivo_iot=:id'),{'id':equipo['device']}).scalar_one()==cantidad
    monkeypatch.setattr(SqlAlchemyAlertaRepository,'actualizar_estado',original)
    # El evaluador comparte recuperación y puede completar el intento fallido.
    h.evaluador(db_session).execute()
    assert alertas(db_session,equipo)[0]['estado_alerta']=='RESUELTA'


def test_recuperacion_automatica_no_se_atribuye_al_operador_de_atencion(client,db_session,equipo,politica):
    h.h.guardar_heartbeat(db_session,equipo,buffer='I')
    perder_contacto(db_session,equipo)
    identificador=alertas(db_session,equipo)[0]['id_alerta']
    uid=db_session.execute(text('SELECT id_usuario FROM modulo1.usuarios LIMIT 1')).scalar_one()
    # now() conserva el inicio de la transacción exterior del fixture. La
    # atención real ocurre después de la generación y debe usar ese instante.
    db_session.execute(text("UPDATE modulo3.alertas SET estado_alerta='EN_ATENCION',id_usuario_atencion=:uid,fecha_atencion=clock_timestamp() WHERE id_alerta=:id"),{'uid':uid,'id':identificador})
    db_session.commit()
    assert client.post('/iot/heartbeat',json=body(equipo)).status_code==200
    construir_procesador(db_session.get_bind(),identidad=False).execute()
    fila=db_session.execute(text("SELECT id_usuario,motivo FROM modulo3.historico_estados_alertas WHERE id_alerta=:id AND estado_nuevo='RESUELTA'"),{'id':identificador}).one()
    assert fila.id_usuario is None and fila.motivo=='Reconexión confirmada por RF-60.'
    assert db_session.execute(text('SELECT id_usuario_atencion FROM modulo3.alertas WHERE id_alerta=:id'),{'id':identificador}).scalar_one()==uid


def test_fallo_auditoria_manual_revierte_estado_e_historia(cliente_manual,db_session,equipo,crear_usuario_db,crear_auth_headers,monkeypatch):
    from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import SqlAlchemyBitacoraAuditoriaIotRepository
    uidrol=db_session.execute(text('SELECT id_rol FROM modulo1.roles WHERE es_protegido')).scalar_one()
    usuario=crear_usuario_db(id_rol=uidrol)
    headers=crear_auth_headers(usuario)
    h.h.guardar_heartbeat(db_session,equipo,buffer='I')
    db_session.execute(text("UPDATE modulo3.estados_dispositivos_iot SET estado_actual='INACTIVO',causa_primaria='FALLO_CONECTIVIDAD' WHERE id_dispositivo_iot=:id"),{'id':equipo['device']});db_session.commit()
    monkeypatch.setattr(SqlAlchemyBitacoraAuditoriaIotRepository,'registrar',lambda self,evento:evento)
    r=cliente_manual.patch(f"/iot/dispositivos/{equipo['device']}/mantenimiento",headers=headers,json={'nuevo_estado':'EN_MANTENIMIENTO'})
    assert r.status_code==503,r.text
    assert db_session.execute(text('SELECT estado_actual FROM modulo3.estados_dispositivos_iot WHERE id_dispositivo_iot=:id'),{'id':equipo['device']}).scalar_one()=='INACTIVO'
    assert db_session.execute(text("SELECT count(*) FROM modulo3.historico_transiciones_dispositivos WHERE id_dispositivo_iot=:id AND estado_nuevo='EN_MANTENIMIENTO'"),{'id':equipo['device']}).scalar_one()==0


@pytest.fixture
def motor_concurrente():
    """Base separada: los commits reales no contaminan los workers de otras pruebas."""
    url=make_url(os.environ['TEST_DATABASE_URL'])
    nombre='dev42_concurrency_test_'+uuid.uuid4().hex
    admin=create_engine(url.set(database='postgres'),isolation_level='AUTOCOMMIT')
    motor=None
    try:
        with admin.connect() as c:
            c.execute(text(f'CREATE DATABASE "{nombre}"'))
        destino=url.set(database=nombre).render_as_string(hide_password=False)
        env=dict(os.environ,DATABASE_URL=destino,ALEMBIC_DATABASE_URL=destino)
        resultado=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],env=env,
            capture_output=True,text=True,timeout=180)
        assert resultado.returncode==0,resultado.stderr[-3000:]
        motor=create_engine(destino)
        yield motor
    finally:
        if motor is not None:
            motor.dispose()
        with admin.connect() as c:
            c.execute(text(f'DROP DATABASE IF EXISTS "{nombre}" WITH (FORCE)'))
        admin.dispose()


def test_bateria_concurrente_reintentos_no_duplican_alerta(motor_concurrente,modelos):
    from src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case import ProcesarHeartbeatPersistidoUseCase
    from src.telemetry.infrastructure.adapters.parametros_heartbeat_mlops_adapter import ParametrosHeartbeatMLOpsAdapter
    from src.telemetry.infrastructure.repositories.alerta_repository import SqlAlchemyAlertaRepository
    from src.telemetry.infrastructure.repositories.heartbeat_repository import SqlAlchemyHeartbeatRepository
    from src.telemetry.infrastructure.models.heartbeat_model import HeartbeatModel
    from src.configuration.application.use_cases.configuracion_global.configurar_parametros_mlops_use_case import ConfigurarParametrosMLOpsUseCase
    from src.prediction.infrastructure.repositories.parametros_mlops_repository import SqlAlchemyParametrosMLOpsRepository
    with Session(motor_concurrente) as db:
        e=h.h.hardware(db)
        uid=db.execute(text('SELECT id_usuario FROM modulo1.usuarios LIMIT 1')).scalar_one()
        ConfigurarParametrosMLOpsUseCase(db,SqlAlchemyParametrosMLOpsRepository(db)).execute(
            {'umbral_bateria_aviso':30,'umbral_bateria_critica':10,'umbral_rssi':-100,'umbral_snr':-10},uid)
        ids=[h.h.guardar_heartbeat(db,e,bateria=b,buffer='I') for b in (20,5)]
    def procesar(identificador):
        with Session(motor_concurrente) as db:
            hb=SqlAlchemyHeartbeatRepository._a_entidad(db.get(HeartbeatModel,identificador))
            ProcesarHeartbeatPersistidoUseCase(None,SqlAlchemyAlertaRepository(db),
                ParametrosHeartbeatMLOpsAdapter(db),None).procesar_alertas(hb,e['area'])
            db.commit()
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(procesar,ids))
    procesar(ids[-1])
    with Session(motor_concurrente) as db:
        filas=alertas(db,e)
        assert len(filas)==1 and filas[0]['severidad']=='CRITICO'
        assert (filas[0]['metadato_evento'] or {}).get('condicion_bateria',filas[0]['tipo_variable'])=='APAGADO_INMINENTE'
        db.execute(text("UPDATE modulo3.estados_dispositivos_iot SET estado_actual='INACTIVO',causa_primaria='FALLO_CONECTIVIDAD' WHERE id_dispositivo_iot=:id"),{'id':e['device']});db.commit()
    def mantenimiento(_):
        from src.shared.errors import BusinessRuleError
        from src.telemetry.application.use_cases.infraestructura.aplicar_mantenimiento_dispositivo_use_case import AplicarMantenimientoDispositivoUseCase
        from src.telemetry.infrastructure.repositories.estado_dispositivo_iot_repository import SqlAlchemyEstadoDispositivoIoTRepository
        from src.telemetry.infrastructure.dto.aplicar_mantenimiento_dto import AplicarMantenimientoDTO
        with Session(motor_concurrente) as db:
            try:
                AplicarMantenimientoDispositivoUseCase(db,SqlAlchemyEstadoDispositivoIoTRepository(db)).execute(
                    e['device'],AplicarMantenimientoDTO(nuevo_estado='EN_MANTENIMIENTO'),uid,'Operador de prueba')
                return 200
            except BusinessRuleError as exc:
                db.rollback()
                return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(mantenimiento,range(2)))==[200,422]
    with Session(motor_concurrente) as db:
        assert db.execute(text("SELECT count(*) FROM modulo3.historico_transiciones_dispositivos WHERE id_dispositivo_iot=:id AND estado_nuevo='EN_MANTENIMIENTO'"),{'id':e['device']}).scalar_one()==1

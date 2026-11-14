# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-26 | Leandro | INC-M03-125-G12 RF-53/63: validar caída real, recuperación automática, FIFO, idempotencia y rollback bajo el rol API. |
"""PostgreSQL local exclusivo. El emisor de prueba conserva las lecturas; no se prueba firmware real."""
import asyncio
from contextlib import suppress
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
import importlib.util
import os
from pathlib import Path
import subprocess
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,text
from sqlalchemy.orm import Session,sessionmaker

from src.shared import database as modulo_db
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import ValidationError
from src.telemetry.infrastructure.routers.telemetria_router import router
from src.telemetry.infrastructure.workers import respaldo_auditoria_iot_worker as worker
from src.telemetry.infrastructure.adapters.respaldo_auditoria_iot_sqlite_adapter import RespaldoAuditoriaIotSqliteAdapter
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import SqlAlchemyBitacoraAuditoriaIotRepository
from src.telemetry.application.use_cases.auditoria.resguardar_falla_persistencia_use_case import ResguardarFallaPersistenciaUseCase
from src.telemetry.application.use_cases.auditoria.sincronizar_respaldo_auditoria_iot_use_case import SincronizarRespaldoAuditoriaIotUseCase
from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import _calcular_hash

_spec=importlib.util.spec_from_file_location('g12_base',Path(__file__).with_name('test_dev05_ingesta_bplus_postcommit.py'))
h=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(h)
modelos=h.modelos
pytestmark=pytest.mark.integration
ROOT=Path(__file__).resolve().parents[2]


@pytest.fixture
def entorno(integration_engine,monkeypatch,tmp_path):
    url=integration_engine.url
    if url.host not in ('127.0.0.1','localhost') or url.database!='sgpmp_g12_test' or url.port!=55427:
        pytest.skip('La caída real exige la base exclusiva local sgpmp_g12_test en 55427.')
    with Session(integration_engine) as db:
        equipo=h.hardware(db);h.calibrar(db,equipo)
        finca=db.execute(text('SELECT id_finca FROM modulo9.infraestructuras WHERE id_infraestructura=:a'),{'a':equipo['area']}).scalar_one()
        servicio=db.execute(text('SELECT modulo1.fn_id_usuario_por_correo(:c)'),{'c':modulo_db.CORREO_USUARIO_SERVICIO}).scalar_one()
        db.execute(text('''INSERT INTO modulo9.usuarios_fincas(id_usuario_finca,id_usuario,id_finca,es_activo)
            SELECT COALESCE(max(id_usuario_finca),0)+1,:u,:f,true FROM modulo9.usuarios_fincas ON CONFLICT (id_usuario,id_finca) DO NOTHING'''),{'u':servicio,'f':finca})
        db.commit()
    motor=create_engine(url,use_insertmanyvalues=False,pool_pre_ping=True,
        connect_args={'connect_timeout':1,'options':'-c role=sgpmp_app'})
    with motor.connect() as c:
        assert c.execute(text('SELECT current_user')).scalar_one()=='sgpmp_app'
        assert c.execute(text("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user")).one()==(False,False)
    monkeypatch.setattr(modulo_db,'SessionLocal',sessionmaker(bind=motor,autoflush=False))
    monkeypatch.setattr(modulo_db,'_id_usuario_servicio',None)
    monkeypatch.setattr(modulo_db,'_PAUSA_REINTENTO',0)
    monkeypatch.setenv('BROKER_SERVICE_TOKEN','g12-real-test-only')
    monkeypatch.setenv('IOT_AUDITORIA_RESPALDO_PATH',str(tmp_path/'fallas.sqlite3'))
    monkeypatch.setenv('IOT_AUDITORIA_RESPALDO_INTERVALO_SEG','1')
    app=FastAPI();register_error_handlers(app);app.include_router(router)
    with TestClient(app,raise_server_exceptions=False,headers={'Authorization':'Bearer g12-real-test-only'}) as cliente:
        yield equipo,cliente,RespaldoAuditoriaIotSqliteAdapter(),motor
    motor.dispose()


def payload(ctx,instante,valor=23,origen='TIEMPO_REAL'):
    return dict(device_id=ctx['device'],sensor_id=ctx['sensor'],serial=ctx['serial'],
        tipo_variable='TEMPERATURA_AMBIENTAL',valor=valor,unidad='°C',timestamp_captura=instante.isoformat(),origen=origen)


def pgctl(accion):
    ruta=os.getenv('G12_PGDATA')
    if not ruta:pytest.skip('Define G12_PGDATA para provocar la caída controlada local.')
    directorio=Path(ruta).resolve()
    assert directorio.is_relative_to((ROOT/'.pytest_cache').resolve()) and (directorio/'PG_VERSION').read_text().strip()=='18'
    comando=['C:/Program Files/PostgreSQL/18/bin/pg_ctl.exe','-D',str(directorio),'-t','120']
    if accion=='stop':comando+=['stop','-m','fast']
    else:comando+=['-l',str(ROOT/'.pytest_cache/g12_postgres.log'),'-o','-p 55427 -h 127.0.0.1','start']
    # En Windows el servidor hereda los pipes de pg_ctl: communicate espera EOF aunque pg_ctl haya terminado.
    with (ROOT/'.pytest_cache/g12_pgctl.log').open('a',encoding='utf-8') as log:
        r=subprocess.run(comando,stdin=subprocess.DEVNULL,stdout=log,stderr=log,text=True,timeout=150)
    assert r.returncode==0,'pg_ctl no completó la operación local solicitada.'


def contar(engine,ids):
    with engine.connect() as db:
        return db.execute(text('SELECT count(*) FROM modulo3.bitacora_auditoria_iot WHERE id_evento=ANY(CAST(:ids AS uuid[]))'),{'ids':[str(i) for i in ids]}).scalar_one()


def sincronizar(cola):
    with modulo_db.sesion_sistema() as db:
        return SincronizarRespaldoAuditoriaIotUseCase(db,SqlAlchemyBitacoraAuditoriaIotRepository(db),cola).execute()


def test_caida_real_20_solicitudes_resguardo_eventos_y_reintento_del_emisor(entorno,integration_engine):
    ctx,cliente,cola,motor=entorno
    base=datetime.now(timezone.utc)-timedelta(minutes=10)
    control=cliente.post('/iot/telemetria',json=payload(ctx,base-timedelta(minutes=1)))
    assert control.status_code==201,control.text
    retenidas=[payload(ctx,base+timedelta(seconds=i*5),23+i/100) for i in range(20)]
    motor.dispose();integration_engine.dispose()
    pgctl('stop')
    try:
        for dato in reversed(retenidas):
            respuesta=cliente.post('/iot/telemetria',json=dato)
            assert respuesta.status_code==503 and respuesta.json()['error_code']=='BD_NO_DISPONIBLE'
            assert 'id_telemetria' not in respuesta.json()
        eventos=cola.listar(100)
        assert len(eventos)==20
        assert [e.accion_detallada['timestamp_captura'] for e in eventos]==[d['timestamp_captura'] for d in reversed(retenidas)]
    finally:
        pgctl('start')
    with integration_engine.connect() as db:
        assert db.execute(text('SELECT count(*) FROM modulo3.telemetrias WHERE id_sensor=:s'),{'s':ctx['sensor']}).scalar_one()==1
    async def recuperacion_automatica():
        tarea=asyncio.create_task(worker.sincronizar_respaldo_auditoria_iot_periodicamente())
        try:
            async def esperar():
                while cola.hay_pendientes():await asyncio.sleep(.05)
            await asyncio.wait_for(esperar(),20)
        finally:
            tarea.cancel()
            with suppress(asyncio.CancelledError):await tarea
    asyncio.run(recuperacion_automatica())
    assert not cola.hay_pendientes()
    assert contar(integration_engine,[e.id_evento for e in eventos])==20
    # El emisor conservó las lecturas. El backend solo respaldó evidencia, sin crear telemetría a partir de ella.
    with integration_engine.connect() as db:
        assert db.execute(text('SELECT count(*) FROM modulo3.telemetrias WHERE id_sensor=:s'),{'s':ctx['sensor']}).scalar_one()==1
    lote={'registros':[dict(d,origen='BUFFER_LOCAL') for d in reversed(retenidas)]}
    reintento=cliente.post('/iot/telemetria/batch',json=lote)
    assert reintento.status_code==200,reintento.text
    assert reintento.json()['aceptados']==20 and reintento.json()['rechazados']==0
    capturas=[i['timestamp_captura'] for i in reintento.json()['detalle']]
    assert [datetime.fromisoformat(t) for t in capturas]==[base+timedelta(seconds=i*5) for i in range(20)]
    duplicado=cliente.post('/iot/telemetria/batch',json=lote)
    assert duplicado.status_code==200 and duplicado.json()['duplicados']==20
    with integration_engine.connect() as db:
        assert db.execute(text('SELECT count(*) FROM modulo3.telemetrias WHERE id_sensor=:s'),{'s':ctx['sensor']}).scalar_one()==21
        filas=db.execute(text('SELECT id_evento,fecha_hora,hash_integridad FROM modulo3.bitacora_auditoria_iot WHERE id_evento=ANY(CAST(:ids AS uuid[]))'),{'ids':[str(e.id_evento) for e in eventos]}).all()
    assert {str(i):(f,h) for i,f,h in filas}=={str(e.id_evento):(e.fecha_hora,e.hash_integridad) for e in eventos}


def test_commit_antes_de_ack_reinicio_no_duplica_auditoria(entorno,integration_engine,monkeypatch):
    ctx,_,cola,_=entorno
    eventos=[ResguardarFallaPersistenciaUseCase(cola).execute('/iot/telemetria',{'device_id':ctx['device'],'indice':i}) for i in range(3)]
    confirmar=cola.confirmar
    monkeypatch.setattr(cola,'confirmar',Mock(side_effect=OSError('confirmación interrumpida')))
    with pytest.raises(OSError):sincronizar(cola)
    assert contar(integration_engine,[e.id_evento for e in eventos])==3 and len(cola.listar(100))==3
    monkeypatch.setattr(cola,'confirmar',confirmar)
    assert sincronizar(RespaldoAuditoriaIotSqliteAdapter(cola.ruta))==3
    assert not cola.hay_pendientes() and contar(integration_engine,[e.id_evento for e in eventos])==3


def test_error_real_de_postgresql_revierte_el_lote_y_conserva_evidencia(entorno,integration_engine):
    ctx,_,cola,_=entorno
    primero=ResguardarFallaPersistenciaUseCase(cola).execute('/iot/telemetria',{'device_id':ctx['device']})
    segundo=ResguardarFallaPersistenciaUseCase(RespaldoAuditoriaIotSqliteAdapter(cola.ruta.with_name('otra.sqlite3'))).execute('/iot/telemetria',{})
    # Provoca una restricción real de longitud sin desactivar triggers ni restricciones.
    segundo.entidad_afectada_id='1'*101;segundo.hash_integridad=_calcular_hash(segundo);cola.guardar(segundo)
    with pytest.raises(ValidationError) as fallo:sincronizar(cola)
    # El traductor oculta el detalle interno al cliente y conserva la excepción SQL como contexto.
    assert getattr(getattr(fallo.value.__context__,'orig',None),'pgcode',None)=='22001'
    assert contar(integration_engine,[primero.id_evento,segundo.id_evento])==0
    assert len(cola.listar(100))==2


def test_recuperadores_concurrentes_son_idempotentes(entorno,integration_engine):
    ctx,_,cola,_=entorno
    eventos=[ResguardarFallaPersistenciaUseCase(cola).execute('/iot/telemetria',{'device_id':ctx['device'],'indice':i}) for i in range(30)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futuros=[pool.submit(sincronizar,RespaldoAuditoriaIotSqliteAdapter(cola.ruta)) for _ in range(2)]
        for futuro in futuros:futuro.result(timeout=30)
    assert not cola.hay_pendientes() and contar(integration_engine,[e.id_evento for e in eventos])==30

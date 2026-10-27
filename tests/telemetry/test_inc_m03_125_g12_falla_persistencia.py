# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-26 | Leandro | INC-M03-125-G12 RF-53/63: validar trazabilidad durable durante caídas sin confirmar lecturas ni sustituir RF-54. |
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from src.shared.database import get_db_sistema
from src.shared.errors import ServiceUnavailableError
from src.shared.error_handlers import register_error_handlers
from src.telemetry.infrastructure.routers import telemetria_router, ruta_ingesta_auditada


@pytest.fixture
def caida(monkeypatch,tmp_path):
    ruta=tmp_path/'fallas.sqlite3'
    monkeypatch.setenv('IOT_AUDITORIA_RESPALDO_PATH',str(ruta))
    monkeypatch.setenv('BROKER_SERVICE_TOKEN','g12-test-only')
    error=OperationalError('NO_MOSTRAR_SQL',{},ConnectionError('NO_MOSTRAR_SECRETO'))
    def sin_bd():
        raise ServiceUnavailableError(code='BD_NO_DISPONIBLE',message='Servicio temporalmente no disponible.',original_error=error)
        yield
    monkeypatch.setattr(ruta_ingesta_auditada,'sesion_sistema',lambda: (_ for _ in ()).throw(error))
    app=FastAPI();register_error_handlers(app);app.include_router(telemetria_router.router)
    app.dependency_overrides[get_db_sistema]=sin_bd
    with TestClient(app,raise_server_exceptions=False) as cliente:
        yield cliente,ruta


def lectura(indice=0):
    return dict(device_id=1,sensor_id=2,tipo_variable='TEMPERATURA_AMBIENTAL',valor=23,
        unidad='°C',serial='serial-sensible',timestamp_captura=(datetime.now(timezone.utc)-timedelta(minutes=20-indice)).isoformat())


def test_veinte_lecturas_fallidas_quedan_trazadas_sin_falso_ack(caida):
    cliente,ruta=caida
    for i in range(20):
        r=cliente.post('/iot/telemetria',json=lectura(i),headers={'Authorization':'Bearer g12-test-only','X-Secreto':'no-guardar'})
        assert r.status_code==503 and r.json()['error_code']=='BD_NO_DISPONIBLE'
        assert 'id_telemetria' not in r.json() and 'NO_MOSTRAR' not in r.text
    assert ruta.exists(), 'No existe respaldo durable de FALLA_PERSISTENCIA.'
    from src.telemetry.infrastructure.adapters.respaldo_auditoria_iot_sqlite_adapter import RespaldoAuditoriaIotSqliteAdapter
    eventos=RespaldoAuditoriaIotSqliteAdapter(ruta).listar(50)
    assert len(eventos)==20 and len({e.id_evento for e in eventos})==20
    assert all(e.tipo_evento=='FALLA_PERSISTENCIA' for e in eventos)
    assert all(e.accion_detallada['sensor_id']==2 for e in eventos)
    contenido=' '.join(json.dumps(e.accion_detallada) for e in eventos)
    assert all(secreto not in contenido for secreto in ['g12-test-only','serial-sensible','no-guardar','NO_MOSTRAR'])


def test_sin_token_no_se_resguarda_una_peticion_no_autorizada(caida):
    cliente,ruta=caida
    assert cliente.post('/iot/telemetria',json=lectura()).status_code==401
    assert not ruta.exists()


def test_lote_fallido_conserva_identificadores_de_las_veinte_lecturas(caida):
    cliente,ruta=caida
    r=cliente.post('/iot/telemetria/batch',json={'registros':[lectura(i) for i in range(20)]},headers={'Authorization':'Bearer g12-test-only'})
    assert r.status_code==503
    from src.telemetry.infrastructure.adapters.respaldo_auditoria_iot_sqlite_adapter import RespaldoAuditoriaIotSqliteAdapter
    [evento]=RespaldoAuditoriaIotSqliteAdapter(ruta).listar(50)
    assert evento.accion_detallada['cantidad_registros']==20
    assert len(evento.accion_detallada['registros'])==20
    assert [r['indice'] for r in evento.accion_detallada['registros']]==list(range(20))


def respaldo(tmp_path):
    from src.telemetry.infrastructure.adapters.respaldo_auditoria_iot_sqlite_adapter import RespaldoAuditoriaIotSqliteAdapter
    return RespaldoAuditoriaIotSqliteAdapter(tmp_path/'respaldo.sqlite3')


def guardar(cola, indice=0):
    from src.telemetry.application.use_cases.auditoria.resguardar_falla_persistencia_use_case import ResguardarFallaPersistenciaUseCase
    return ResguardarFallaPersistenciaUseCase(cola).execute('/iot/telemetria',{'device_id':1,'sensor_id':2,'indice':indice})


def caso(db,destino,cola):
    from src.telemetry.application.use_cases.auditoria.sincronizar_respaldo_auditoria_iot_use_case import SincronizarRespaldoAuditoriaIotUseCase
    return SincronizarRespaldoAuditoriaIotUseCase(db,destino,cola)


def test_reinicio_del_adaptador_preserva_uuid_fecha_hash_y_fifo(tmp_path):
    from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import _calcular_hash
    cola=respaldo(tmp_path)
    originales=[guardar(cola,i) for i in range(20)]
    recuperados=respaldo(tmp_path).listar(100)
    assert [e.id_evento for e in recuperados]==[e.id_evento for e in originales]
    assert [e.fecha_hora for e in recuperados]==[e.fecha_hora for e in originales]
    assert all(_calcular_hash(e)==e.hash_integridad for e in recuperados)
    assert all(e.clasificacion_registro=='NIC41' and e.retencion_aplicable==5 for e in recuperados)


def test_escritores_concurrentes_no_pierden_evidencia(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    cola=respaldo(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids=list(pool.map(lambda i:guardar(cola,i).id_evento,range(40)))
    assert {e.id_evento for e in cola.listar(100)}==set(ids) and len(ids)==40


@pytest.mark.parametrize('fallo',['segundo_evento','commit'])
def test_fallo_destino_o_commit_conserva_todo_el_lote(tmp_path,fallo):
    cola=respaldo(tmp_path);esperados=[guardar(cola,i).id_evento for i in range(2)]
    db=Mock();destino=Mock();destino.bloquear_respaldo.return_value=True
    if fallo=='segundo_evento':destino.registrar_respaldo.side_effect=[None,RuntimeError('sin destino')]
    else:db.commit.side_effect=RuntimeError('sin commit')
    with pytest.raises(RuntimeError):caso(db,destino,cola).execute()
    db.rollback.assert_called_once()
    assert [e.id_evento for e in cola.listar(100)]==esperados


def test_confirmacion_ocurre_despues_del_commit_y_respeta_lote(tmp_path):
    cola=respaldo(tmp_path);eventos=[guardar(cola,i) for i in range(3)]
    db=Mock();destino=Mock();destino.bloquear_respaldo.return_value=True
    # La evidencia todavía debe estar en disco cuando PostgreSQL confirma.
    def confirmar_commit():assert len(cola.listar(100))==3
    db.commit.side_effect=confirmar_commit
    assert caso(db,destino,cola).execute(limite=2)==2
    assert [c.args[0].id_evento for c in destino.registrar_respaldo.call_args_list]==[e.id_evento for e in eventos[:2]]
    assert [e.id_evento for e in cola.listar(100)]==[eventos[2].id_evento]


def test_error_confirmacion_local_no_borra_el_respaldo(tmp_path,monkeypatch):
    cola=respaldo(tmp_path);evento=guardar(cola)
    monkeypatch.setattr(cola,'confirmar',Mock(side_effect=OSError('disco no disponible')))
    db=Mock();destino=Mock();destino.bloquear_respaldo.return_value=True
    with pytest.raises(OSError):caso(db,destino,cola).execute()
    db.commit.assert_called_once()
    assert cola.listar(100)[0].id_evento==evento.id_evento


def test_otro_recuperador_tiene_el_bloqueo_no_consume_la_cola(tmp_path):
    cola=respaldo(tmp_path);guardar(cola)
    db=Mock();destino=Mock();destino.bloquear_respaldo.return_value=False
    assert caso(db,destino,cola).execute()==0
    assert cola.hay_pendientes()
    destino.registrar_respaldo.assert_not_called();db.commit.assert_not_called()


def test_respaldo_alterado_no_se_borra_ni_llega_al_destino(tmp_path):
    import sqlite3
    cola=respaldo(tmp_path);guardar(cola)
    with sqlite3.connect(str(cola.ruta)) as db:
        contenido=db.execute('SELECT contenido FROM pendientes').fetchone()[0]
        datos=json.loads(contenido);datos['accion_detallada']['sensor_id']=999
        db.execute('UPDATE pendientes SET contenido=?',(json.dumps(datos),))
    db=Mock();destino=Mock();destino.bloquear_respaldo.return_value=True
    with pytest.raises(ValueError,match='Integridad'):caso(db,destino,cola).execute()
    assert cola.hay_pendientes();destino.registrar_respaldo.assert_not_called()


def test_fallo_del_disco_es_visible_sin_convertir_503_en_exito(caida,monkeypatch,caplog):
    from src.telemetry.infrastructure.adapters.respaldo_auditoria_iot_sqlite_adapter import RespaldoAuditoriaIotSqliteAdapter
    monkeypatch.setattr(RespaldoAuditoriaIotSqliteAdapter,'guardar',Mock(side_effect=OSError('no-registrar-secreto')))
    cliente,_=caida
    r=cliente.post('/iot/telemetria',json=lectura(),headers={'Authorization':'Bearer g12-test-only'})
    assert r.status_code==503
    assert any(rec.levelname=='CRITICAL' and 'sin respaldo durable' in rec.message for rec in caplog.records)
    assert 'no-registrar-secreto' not in r.text


def test_recuperador_sin_pendientes_no_abre_postgresql(tmp_path,monkeypatch):
    from src.telemetry.infrastructure.workers import respaldo_auditoria_iot_worker as worker
    monkeypatch.setenv('IOT_AUDITORIA_RESPALDO_PATH',str(tmp_path/'vacio.sqlite3'))
    abrir=Mock();monkeypatch.setattr(worker,'sesion_sistema',abrir)
    assert worker.sincronizar_respaldo()==0
    abrir.assert_not_called()


def test_apagado_espera_el_hilo_y_no_oculta_la_cancelacion(monkeypatch):
    import asyncio
    from threading import Event
    from src.telemetry.infrastructure.workers import respaldo_auditoria_iot_worker as worker
    iniciado,liberar=Event(),Event()
    def recuperacion_interrumpida():
        iniciado.set()
        assert liberar.wait(timeout=3)
        raise RuntimeError('BD sigue caída')
    monkeypatch.setattr(worker,'sincronizar_respaldo',recuperacion_interrumpida)
    async def ejecutar():
        tarea=asyncio.create_task(worker.sincronizar_respaldo_auditoria_iot_periodicamente())
        while not iniciado.is_set():await asyncio.sleep(.01)
        tarea.cancel();liberar.set()
        with pytest.raises(asyncio.CancelledError):await tarea
    asyncio.run(ejecutar())


def test_fecha_extrema_sin_validar_no_sustituye_el_503_original(caida):
    cliente,ruta=caida
    dato=lectura();dato['timestamp_captura']='9999-12-31T23:59:59-23:59'
    r=cliente.post('/iot/telemetria',json=dato,headers={'Authorization':'Bearer g12-test-only'})
    assert r.status_code==503 and ruta.exists()


def test_tarea_periodica_invoca_el_recuperador_sin_intervencion_http(monkeypatch):
    import asyncio
    from src.telemetry.infrastructure.workers import respaldo_auditoria_iot_worker as worker
    ejecutar=Mock(return_value=20)
    monkeypatch.setattr(worker,'sincronizar_respaldo',ejecutar)
    async def comprobar():
        tarea=asyncio.create_task(worker.sincronizar_respaldo_auditoria_iot_periodicamente())
        try:
            async def esperar():
                while not ejecutar.called:await asyncio.sleep(.01)
            await asyncio.wait_for(esperar(),2)
        finally:
            tarea.cancel()
            with pytest.raises(asyncio.CancelledError):await tarea
    asyncio.run(comprobar())
    ejecutar.assert_called_once()

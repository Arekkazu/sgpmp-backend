# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-27 RF-60: integra politica, HTTP y postcommit |
# | 2026-10-22 | Leandro | DEV-42 RF-60: verifica apagado y escalamiento con tipo inmutable |
"""PostgreSQL aislado: parámetros reales y mismo worker HTTP/SQL, sin broker real."""
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.configuration.domain.entities.parametros_heartbeat import (
    BATERIA_AVISO, BATERIA_CRITICA, COBERTURA, DURACION, FIRMWARE,
    INACTIVIDAD, INTERVALO_CAMARA, LATENCIA, MARGEN, PREDETERMINADOS_HEARTBEAT,
    RSSI, SNR, TEMPERATURA_CRITICA, TEMPERATURA_MAXIMA, VENTANAS,
)
from src.configuration.infrastructure.routers import configuracion_global_router
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.identity_access.domain.entities.cuenta import Cuenta
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import ValidationError
from src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case import EvaluarEstadoDispositivosUseCase
from src.telemetry.infrastructure.adapters.parametros_heartbeat_mlops_adapter import (
    DiagnosticoHeartbeatMLOpsAdapter, ParametrosHeartbeatMLOpsAdapter,
)
from src.telemetry.infrastructure.repositories.alerta_repository import SqlAlchemyAlertaRepository
from src.telemetry.infrastructure.repositories.estado_dispositivo_iot_repository import SqlAlchemyEstadoDispositivoIoTRepository
from src.telemetry.infrastructure.repositories.periodo_inactividad_repository import SqlAlchemyPeriodoInactividadRepository
from src.telemetry.infrastructure.workers.postcommit_worker import construir_procesador

_spec = importlib.util.spec_from_file_location('dev27_base', Path(__file__).with_name('test_dev05_ingesta_bplus_postcommit.py'))
h = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h)
modelos = h.modelos
equipo = h.equipo
client = h.client
parametros_rf60 = h.parametros_rf60
pytestmark = pytest.mark.integration


@pytest.fixture
def politica(parametros_rf60):
    writer, usuario = parametros_rf60
    # Valores deliberados de prueba, no semillas normativas.
    writer.execute({BATERIA_AVISO:30, BATERIA_CRITICA:10, RSSI:-100, SNR:-10,
                    TEMPERATURA_MAXIMA:40, TEMPERATURA_CRITICA:50, FIRMWARE:'1.10.0'}, usuario)
    return writer, usuario


def filas_alertas(db, equipo):
    return db.execute(text('''SELECT id_alerta,tipo_variable,severidad,metadato_evento
        FROM modulo3.alertas WHERE id_dispositivo_ioit=:id ORDER BY id_alerta'''),
        {'id':equipo['device']}).mappings().all()


def test_http_y_sql_completan_diagnostico_real_sin_duplicados(client, db_session, equipo, politica):
    otro = h.hardware(db_session)
    body = dict(device_id=equipo['device'], serial=equipo['serial'], tipo_mensaje='HEARTBEAT',
                estado_local_buffer='I', fecha_registro=datetime.now(timezone.utc).isoformat(),
                nivel_bateria_pct=5, calidad_senal_snr=-15, temperatura_dispositivo=55,
                version_firmware='1.9.0', sensores_operativos=[{'sensor':'humedad','operativo':False}])
    response = client.post('/iot/heartbeat', json=body)
    assert response.status_code == 200, response.text
    id_http = response.json()['id_heartbeat']
    id_sql = db_session.execute(text('''INSERT INTO modulo3.heartbeats
        (id_dispositivo_iot,tipo_mensaje,estado_local_buffer,fecha_registro,fecha_recepcion,
         nivel_bateria_pct,calidad_senal_snr,temperatura_dispositivo,version_firmware,json_sensores_operativos)
        VALUES (:id,'HEARTBEAT','I',now(),now(),5,-15,55,'1.9.0',
          CAST(:sensores AS jsonb)) RETURNING id_heartbeat'''),
        {'id':otro['device'],'sensores':json.dumps([{'sensor':'humedad','operativo':False}])}).scalar_one()
    db_session.commit()
    assert not filas_alertas(db_session, equipo) and not filas_alertas(db_session, otro)
    worker = construir_procesador(db_session.get_bind(), identidad=False)
    worker.execute()
    worker.execute()
    for dispositivo, identificador in ((equipo,id_http),(otro,id_sql)):
        alertas = filas_alertas(db_session, dispositivo)
        assert {a['tipo_variable'] for a in alertas} == {
            'APAGADO_INMINENTE','SEÑAL_DEGRADADA','SENSOR_FISICO_FALLIDO',
            'SOBRECALENTAMIENTO','FIRMWARE_DESACTUALIZADO'}
        assert len(alertas) == 5
        assert next(a for a in alertas if a['tipo_variable']=='SOBRECALENTAMIENTO')['severidad']=='CRITICO'
        eventos = h.evidencias(db_session, identificador, 'HEARTBEAT')
        assert len(eventos) == 5 and all(e['tipo_evento'].endswith('_COMPLETADO') for e in eventos)
        for alerta in alertas:
            assert db_session.execute(text('SELECT count(*) FROM modulo3.historico_estados_alertas WHERE id_alerta=:id'), {'id':alerta['id_alerta']}).scalar_one()==1


def test_parametros_persistidos_cambian_mismo_consumidor_sin_reinicio(db_session, equipo, politica):
    writer, usuario = politica
    adaptador = ParametrosHeartbeatMLOpsAdapter(db_session)
    diagnostico = DiagnosticoHeartbeatMLOpsAdapter(db_session)
    assert adaptador.obtener().bateria_critica == 10
    assert diagnostico.comparar_firmware(equipo['device'],'1.9.0').es_anterior
    inicial = adaptador.obtener_comunicacion(equipo['device'])
    writer.execute({BATERIA_CRITICA:25, FIRMWARE:'1.8.0', MARGEN:400, INACTIVIDAD:4000,
                    TEMPERATURA_MAXIMA:60, TEMPERATURA_CRITICA:70}, usuario)
    assert adaptador.obtener().bateria_critica == 25
    assert not diagnostico.comparar_firmware(equipo['device'],'1.9.0').es_anterior
    assert diagnostico.obtener_umbrales_temperatura(equipo['device']).maximo_operativo == 60
    posterior = adaptador.obtener_comunicacion(equipo['device'])
    assert (inicial.umbral_sin_senal, posterior.umbral_sin_senal)==(900,1000)
    assert posterior.umbral_inactivo == 5000


def test_cambio_bd_modifica_alerta_en_mismo_worker(db_session,equipo,politica):
    writer, usuario = politica
    worker = construir_procesador(db_session.get_bind(),identidad=False)
    h.guardar_heartbeat(db_session,equipo,bateria=20,buffer='I')
    worker.execute()
    assert [a['tipo_variable'] for a in filas_alertas(db_session,equipo)]==['BATERIA_BAJA']
    writer.execute({BATERIA_CRITICA:25},usuario)
    h.guardar_heartbeat(db_session,equipo,bateria=20,buffer='I')
    worker.execute()
    assert [(a['tipo_variable'],a['severidad']) for a in filas_alertas(db_session,equipo)]==[
        ('BATERIA_BAJA','CRITICO')]


def test_telemetria_mas_reciente_confirma_contacto_aunque_heartbeat_sea_antiguo(db_session,equipo,politica):
    identificador = h.guardar_heartbeat(db_session,equipo,buffer='I',
        fecha=datetime.now(timezone.utc)-timedelta(minutes=20))
    h.calibrar(db_session,equipo)
    h.sql_ingesta(db_session,equipo)
    contacto = db_session.execute(text('SELECT fecha_ultimo_contacto FROM modulo3.estados_dispositivos_iot WHERE id_dispositivo_iot=:id'), {'id':equipo['device']}).scalar_one()
    assert contacto > datetime.now(timezone.utc)-timedelta(minutes=1)
    worker = construir_procesador(db_session.get_bind(),identidad=False)
    worker.execute()
    estado = db_session.execute(text('SELECT estado_actual,fecha_ultimo_contacto FROM modulo3.estados_dispositivos_iot WHERE id_dispositivo_iot=:id'), {'id':equipo['device']}).one()
    assert tuple(estado)==('ACTIVO',contacto)
    assert any(e['tipo_evento']=='POSTCOMMIT_HEARTBEAT_ESTADO_COMPLETADO'
        for e in h.evidencias(db_session,identificador,'HEARTBEAT'))


def test_falta_parametro_deja_etapa_pendiente_y_recupera_tras_configurar(db_session,equipo,parametros_rf60):
    writer, usuario = parametros_rf60
    worker = construir_procesador(db_session.get_bind(),identidad=False,reintento_seg=1)
    identificador = h.guardar_heartbeat(db_session,equipo,bateria=5,buffer='I')
    worker.execute()
    eventos = h.evidencias(db_session,identificador,'HEARTBEAT')
    assert any(e['tipo_evento']=='POSTCOMMIT_HEARTBEAT_ALERTAS_FALLIDO' and
               e['accion_detallada']['error']=='PARAMETRO_CONFIGURACION_AUSENTE' for e in eventos)
    assert not filas_alertas(db_session,equipo)
    writer.execute({BATERIA_AVISO:30,BATERIA_CRITICA:10,RSSI:-100,SNR:-10},usuario)
    time.sleep(1.1)
    worker.execute()
    worker.execute()
    assert [a['tipo_variable'] for a in filas_alertas(db_session,equipo)]==['APAGADO_INMINENTE']
    assert sum(e['tipo_evento']=='POSTCOMMIT_HEARTBEAT_ALERTAS_COMPLETADO'
        for e in h.evidencias(db_session,identificador,'HEARTBEAT'))==1


def evaluador(db):
    return EvaluarEstadoDispositivosUseCase(db, SqlAlchemyEstadoDispositivoIoTRepository(db),
        None, SqlAlchemyPeriodoInactividadRepository(db), SqlAlchemyAlertaRepository(db), None, ParametrosHeartbeatMLOpsAdapter(db))


def test_heartbeat_antiguo_genera_sin_senal_y_telemetria_recupera_periodo(db_session,equipo,politica):
    identificador = h.guardar_heartbeat(db_session,equipo,buffer='I',
        fecha=datetime.now(timezone.utc)-timedelta(minutes=20))
    worker = construir_procesador(db_session.get_bind(),identidad=False)
    worker.execute()
    worker.execute()
    assert [(a['tipo_variable'],a['severidad']) for a in filas_alertas(db_session,equipo)]==[('DISPOSITIVO_SIN_SEÑAL','LEVE')]
    assert any(e['tipo_evento']=='POSTCOMMIT_HEARTBEAT_ESTADO_COMPLETADO'
        for e in h.evidencias(db_session,identificador,'HEARTBEAT'))
    assert db_session.execute(text('SELECT count(*) FROM modulo3.periodos_inactividad WHERE id_dispositivo_iot=:id AND fecha_fin IS NULL'), {'id':equipo['device']}).scalar_one()==1
    h.calibrar(db_session,equipo)
    h.sql_ingesta(db_session,equipo)
    evaluador(db_session).execute()
    assert db_session.execute(text('SELECT estado_actual FROM modulo3.estados_dispositivos_iot WHERE id_dispositivo_iot=:id'), {'id':equipo['device']}).scalar_one()=='ACTIVO'
    assert db_session.execute(text('SELECT count(*) FROM modulo3.periodos_inactividad WHERE id_dispositivo_iot=:id AND fecha_fin IS NULL'), {'id':equipo['device']}).scalar_one()==0


def test_evaluacion_periodica_escala_inactivo_critico_con_un_historial(db_session, equipo, politica):
    h.guardar_heartbeat(db_session, equipo, buffer='I')
    db_session.execute(text('UPDATE modulo3.estados_dispositivos_iot SET fecha_ultimo_contacto=:ts WHERE id_dispositivo_iot=:id'),
        {'id':equipo['device'],'ts':datetime.now(timezone.utc)-timedelta(seconds=1000)})
    db_session.commit()
    uc = evaluador(db_session)
    uc.execute()
    assert [a['tipo_variable'] for a in filas_alertas(db_session,equipo)] == ['DISPOSITIVO_SIN_SEÑAL']
    db_session.execute(text('UPDATE modulo3.estados_dispositivos_iot SET fecha_ultimo_contacto=:ts WHERE id_dispositivo_iot=:id'),
        {'id':equipo['device'],'ts':datetime.now(timezone.utc)-timedelta(seconds=5000)})
    db_session.commit()
    uc.execute()
    uc.execute()
    alertas = filas_alertas(db_session,equipo)
    assert [(a['tipo_variable'],a['severidad']) for a in alertas]==[
        ('DISPOSITIVO_SIN_SEÑAL','LEVE'),('DISPOSITIVO_INACTIVO','CRITICO')]
    historico = db_session.execute(text('''SELECT estado_nuevo,count(*) FROM modulo3.historico_transiciones_dispositivos
        WHERE id_dispositivo_iot=:id GROUP BY estado_nuevo'''), {'id':equipo['device']}).all()
    assert ('SIN_SEÑAL',1) in historico and ('INACTIVO',1) in historico


def test_fallo_alerta_revierte_estado_historial_y_periodo(db_session, equipo, politica, monkeypatch):
    h.guardar_heartbeat(db_session,equipo,buffer='I')
    db_session.execute(text('UPDATE modulo3.estados_dispositivos_iot SET fecha_ultimo_contacto=now()-interval \'2 hours\' WHERE id_dispositivo_iot=:id'), {'id':equipo['device']})
    db_session.commit()
    def snapshot():
        return db_session.execute(text('SELECT to_jsonb(e) FROM modulo3.estados_dispositivos_iot e WHERE id_dispositivo_iot=:id'), {'id':equipo['device']}).scalar_one()
    antes = snapshot()
    def fallar(*args):
        raise RuntimeError('Fallo de persistencia de prueba')
    monkeypatch.setattr(SqlAlchemyAlertaRepository,'guardar',fallar)
    with pytest.raises(RuntimeError):
        evaluador(db_session).execute()
    assert snapshot() == antes
    assert not filas_alertas(db_session,equipo)
    assert db_session.execute(text('SELECT count(*) FROM modulo3.historico_transiciones_dispositivos WHERE id_dispositivo_iot=:id AND estado_nuevo=\'INACTIVO\''), {'id':equipo['device']}).scalar_one()==0
    assert db_session.execute(text('SELECT count(*) FROM modulo3.periodos_inactividad WHERE id_dispositivo_iot=:id'), {'id':equipo['device']}).scalar_one()==0


@pytest.mark.parametrize('frecuencia,heartbeat,status', [(3,20,400),(10,9,400),(20,30,400),(8,20,200)])
def test_patch_rf18_valida_cadena_sin_alterar_rechazos(db_session, parametros_rf60, frecuencia, heartbeat,status):
    uid, rol = db_session.execute(text("SELECT u.id_usuario,u.id_rol FROM modulo1.usuarios u JOIN modulo1.roles r USING(id_rol) WHERE lower(r.nombre_rol)='administrador' LIMIT 1")).one()
    actual = db_session.execute(text('SELECT id_configuracion_global,fecha_actualizacion,frecuencia_muestreo,heartbeat FROM modulo9.configuraciones_globales WHERE es_activo')).mappings().one()
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(configuracion_global_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(uid,1,rol,Cuenta.ESTADO_ACTIVO)
    with TestClient(app,raise_server_exceptions=False) as cliente:
        respuesta = cliente.patch('/configuracion/parametros/'+str(actual['id_configuracion_global']), json={
            'frecuencia_muestreo':frecuencia,'umbral_sin_senal':heartbeat,
            'fecha_actualizacion':actual['fecha_actualizacion'].isoformat()})
    assert respuesta.status_code==status, respuesta.text
    if status==400:
        assert respuesta.json()['error_code'] in ('CADENA_HEARTBEAT_INVALIDA','HEARTBEAT_MENOR_FRECUENCIA')
    db_session.rollback()
    posterior = db_session.execute(text('SELECT frecuencia_muestreo,heartbeat FROM modulo9.configuraciones_globales WHERE es_activo')).one()
    assert tuple(posterior)==((actual['frecuencia_muestreo'],actual['heartbeat']) if status==400 else (frecuencia,heartbeat))


def test_camara_usa_intervalo_canonico_y_relee_cambios(db_session,equipo,parametros_rf60):
    writer, usuario = parametros_rf60
    tipo = db_session.execute(text("SELECT id_tipo_dispositivo FROM modulo9.tipos_dispositivo_iot WHERE categoria='CAMARA' LIMIT 1")).scalar_one()
    db_session.execute(text('UPDATE modulo9.dispositivos_iot SET id_tipo_dispositivo=:tipo WHERE id_dispositivo_iot=:id'), {'tipo':tipo,'id':equipo['device']})
    db_session.commit()
    adapter = ParametrosHeartbeatMLOpsAdapter(db_session)
    assert adapter.obtener_comunicacion(equipo['device']).intervalo_heartbeat_seg == 120
    writer.execute({INTERVALO_CAMARA:200},usuario)
    assert adapter.obtener_comunicacion(equipo['device']).intervalo_heartbeat_seg == 200


def test_configuracion_invalida_no_persiste_parcialmente(db_session,parametros_rf60):
    writer, usuario = parametros_rf60
    with pytest.raises(ValidationError):
        writer.execute({INTERVALO_CAMARA:301, VENTANAS:4},usuario)
    assert db_session.execute(text('SELECT valor_actual FROM modulo4.parametros_mlops WHERE nombre_parametro=:n'), {'n':INTERVALO_CAMARA}).scalar_one()==120
    assert db_session.execute(text('SELECT count(*) FROM modulo4.parametros_mlops WHERE nombre_parametro=:n'), {'n':VENTANAS}).scalar_one()==0


def test_cli_siembra_idempotente_conserva_y_actualiza_solo_explicitos(integration_engine,tmp_path):
    # CLI en otra conexión: se confirma únicamente en esta BD efímera local.
    nombres = list(PREDETERMINADOS_HEARTBEAT)
    with integration_engine.connect() as c:
        usuario = c.execute(text("SELECT u.id_usuario FROM modulo1.usuarios u JOIN modulo1.roles r USING(id_rol) WHERE lower(r.nombre_rol)='administrador' LIMIT 1")).scalar_one()
        antes = c.execute(text('SELECT nombre_parametro,valor_actual FROM modulo4.parametros_mlops WHERE nombre_parametro=ANY(:ns)'), {'ns':nombres}).all()
        activa = c.execute(text('SELECT id_configuracion_global FROM modulo9.configuraciones_globales WHERE es_activo')).scalar_one_or_none()
    config_creada = None
    if activa is None:
        with integration_engine.begin() as c:
            config_creada = c.execute(text('''INSERT INTO modulo9.configuraciones_globales(frecuencia_muestreo,heartbeat,fecha_actualizacion,id_usuario,es_activo)
                VALUES(10,20,now(),:u,true) RETURNING id_configuracion_global'''), {'u':usuario}).scalar_one()
    env = dict(os.environ, DEV14_DATABASE_URL=integration_engine.url.render_as_string(hide_password=False), PYTHONIOENCODING='utf-8')
    args = [sys.executable,'scripts/configurar_parametros_dev14.py','--sembrar-heartbeat','--id-usuario',str(usuario)]
    def ejecutar(*extras):
        r = subprocess.run(args+list(extras),env=env,capture_output=True,text=True,encoding='utf-8',timeout=30)
        assert r.returncode==0,r.stderr
        return r.stdout
    try:
        assert 'Simulación' in ejecutar()
        ejecutar('--aplicar')
        assert ejecutar('--aplicar').count('conservado')==5
        archivo = tmp_path/'parametros.json'
        archivo.write_text(json.dumps({VENTANAS:5}),encoding='utf-8')
        assert 'actualizado' in ejecutar('--archivo',str(archivo),'--actualizar-existentes','--aplicar')
        with integration_engine.connect() as c:
            fila = c.execute(text('SELECT valor_actual,valor_por_defecto FROM modulo4.parametros_mlops WHERE nombre_parametro=:n'), {'n':VENTANAS}).one()
            assert tuple(fila)==(5,3)
            assert c.execute(text('SELECT count(*) FROM modulo4.parametros_mlops WHERE nombre_parametro=ANY(:ns)'), {'ns':nombres}).scalar_one()==5
    finally:
        with integration_engine.begin() as c:
            c.execute(text('DELETE FROM modulo4.parametros_mlops WHERE nombre_parametro=ANY(:ns)'), {'ns':nombres})
            for nombre, valor in antes:
                c.execute(text('INSERT INTO modulo4.parametros_mlops(nombre_parametro,valor_actual,valor_por_defecto) VALUES(:n,CAST(:v AS jsonb),CAST(:v AS jsonb))'), {'n':nombre,'v':json.dumps(valor)})
            if config_creada:
                c.execute(text('UPDATE modulo9.configuraciones_globales SET es_activo=false WHERE id_configuracion_global=:id'), {'id':config_creada})

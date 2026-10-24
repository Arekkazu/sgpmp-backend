"""HTTP y escritura SQL del broker → mismo worker, PostgreSQL con DB-03.

La política térmica/firmware se dobla donde se indica: no representa una
configuración M09 disponible ni una entrega real desde el broker/firmware.
"""
from datetime import datetime, timezone
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import time
from unittest.mock import Mock

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.errors import ServiceUnavailableError
from src.telemetry.domain.repositories.diagnostico_heartbeat_port import ComparacionFirmware, UmbralesTemperaturaDispositivo
from src.telemetry.infrastructure.workers.postcommit_worker import construir_procesador
from src.telemetry.domain.repositories.postcommit_port import EtapaPostcommit
from src.telemetry.infrastructure.repositories.postcommit_repository import unidad_postcommit

_spec=importlib.util.spec_from_file_location('dev12_base_dev05',Path(__file__).with_name('test_dev05_ingesta_bplus_postcommit.py'))
h=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h)
modelos=h.modelos
equipo=h.equipo
client=h.client
pytestmark=pytest.mark.integration


@pytest.fixture(autouse=True)
def esquema_db03(integration_engine):
    with integration_engine.connect() as c:
        columnas=set(c.execute(text("SELECT column_name FROM information_schema.columns WHERE table_schema='modulo3' AND table_name='heartbeats'")).scalars())
    if not {'json_sensores_operativos','temperatura_dispositivo'}<=columnas:
        pytest.skip('Requiere DB-03 65541db23c71; las pruebas no alteran el esquema por su cuenta.')


def payload(**cambios):
    return dict(tipo_mensaje='HEARTBEAT',fecha_registro=datetime.now(timezone.utc).isoformat(),
                estado_local_buffer='I',**cambios)


def enviar_http(client,equipo,**cambios):
    return client.post('/iot/heartbeat',json=payload(device_id=equipo['device'],serial=equipo['serial'],**cambios))


def insertar_sql(db,equipo,**cambios):
    valores=dict(d=equipo['device'],s=None,t=None,v=None)|cambios
    if valores['s'] is not None: valores['s']=json.dumps(valores['s'])
    identificador=db.execute(text('''INSERT INTO modulo3.heartbeats(id_dispositivo_iot,tipo_mensaje,
        estado_local_buffer,datos_pendientes_buffer,fecha_registro,fecha_recepcion,reloj_sincronizado,
        json_sensores_operativos,temperatura_dispositivo,version_firmware)
        VALUES (:d,'HEARTBEAT','I',0,now(),now(),true,CAST(:s AS jsonb),:t,:v) RETURNING id_heartbeat'''),valores).scalar_one()
    db.commit()
    return identificador


def procesar(db,politica=None):
    return construir_procesador(db.get_bind(),identidad=False,diagnostico_heartbeat=politica,reintento_seg=1).execute()


def alertas(db,equipo):
    return db.execute(text('''SELECT id_alerta,tipo_variable,severidad,metadato_evento
        FROM modulo3.alertas WHERE id_dispositivo_ioit=:id ORDER BY id_alerta'''),{'id':equipo['device']}).mappings().all()


@pytest.mark.parametrize('sensores',[None,[],[{'sensor':'humedad','operativo':True}]])
def test_http_compatible_y_sin_falsos_fallos(client,db_session,equipo,sensores):
    response=enviar_http(client,equipo,sensores_operativos=sensores)
    assert response.status_code==200,response.text
    assert response.json()['sensores_operativos']==sensores
    procesar(db_session)
    assert alertas(db_session,equipo)==[]
    fila=db_session.execute(text('SELECT json_sensores_operativos,temperatura_dispositivo FROM modulo3.heartbeats WHERE id_heartbeat=:id'),{'id':response.json()['id_heartbeat']}).one()
    assert fila[0]==sensores and fila[1] is None


def test_http_sin_campos_nuevos_conserva_contrato_y_estado(client,db_session,equipo):
    response=enviar_http(client,equipo)
    assert response.status_code==200,response.text
    procesar(db_session)
    assert db_session.execute(text('SELECT estado_actual FROM modulo3.estados_dispositivos_iot WHERE id_dispositivo_iot=:id'),{'id':equipo['device']}).scalar_one()=='ACTIVO'
    assert alertas(db_session,equipo)==[]


@pytest.mark.parametrize('campos',[{'sensores_operativos':[{'sensor':'x','operativo':'false'}]},
    {'sensores_operativos':{}},{'temperatura_dispositivo':'caliente'},{'temperatura_dispositivo':1000}])
def test_http_invalido_no_persiste(client,db_session,equipo,campos):
    response=enviar_http(client,equipo,**campos)
    assert response.status_code==400,response.text
    assert db_session.execute(text('SELECT count(*) FROM modulo3.heartbeats WHERE id_dispositivo_iot=:id'),{'id':equipo['device']}).scalar_one()==0


def test_identidad_invalida_conserva_rechazo_http(client,db_session,equipo):
    response=client.post('/iot/heartbeat',json=payload(device_id=equipo['device'],serial='no-autorizado',
        sensores_operativos=[{'sensor':'x','operativo':False}]))
    assert response.status_code==401,response.text
    assert not alertas(db_session,equipo)


def test_http_y_sql_comparten_evaluacion_postcommit_y_trazabilidad(client,db_session,equipo):
    segundo=h.hardware(db_session)
    sensores=[{'sensor':'humedad','operativo':False},{'sensor':'temperatura','operativo':True}]
    response=enviar_http(client,equipo,sensores_operativos=sensores)
    assert response.status_code==200,response.text
    id_http=response.json()['id_heartbeat']
    id_sql=insertar_sql(db_session,segundo,s=sensores)
    # La aceptación HTTP solo confirma la fila. No adelanta efectos del worker.
    assert not alertas(db_session,equipo) and not alertas(db_session,segundo)
    procesar(db_session);procesar(db_session)
    for dispositivo,identificador in [(equipo,id_http),(segundo,id_sql)]:
        filas=alertas(db_session,dispositivo)
        assert len(filas)==1 and filas[0]['tipo_variable']=='SENSOR_FISICO_FALLIDO'
        assert filas[0]['metadato_evento']=={'id_heartbeat':identificador,'sensores_fallidos':['humedad']}
        assert db_session.execute(text('SELECT count(*) FROM modulo3.historico_estados_alertas WHERE id_alerta=:id'),{'id':filas[0]['id_alerta']}).scalar_one()==1
        assert any(x['tipo_evento']=='POSTCOMMIT_HEARTBEAT_SENSORES_COMPLETADO' for x in h.evidencias(db_session,identificador,'HEARTBEAT'))


def test_reintentos_y_otro_heartbeat_no_duplican_pero_otro_sensor_no_se_suprime(db_session,equipo):
    sensores=[{'sensor':'humedad','operativo':False},{'sensor':'ph','operativo':False}]
    insertar_sql(db_session,equipo,s=list(reversed(sensores)));procesar(db_session)
    insertar_sql(db_session,equipo,s=sensores);procesar(db_session)
    assert len(alertas(db_session,equipo))==1
    insertar_sql(db_session,equipo,s=[{'sensor':'temperatura','operativo':False}]);procesar(db_session)
    assert len(alertas(db_session,equipo))==2


def test_fallo_configuracion_no_bloquea_sensor_ni_pierde_heartbeat(db_session,equipo):
    identificador=insertar_sql(db_session,equipo,s=[{'sensor':'x','operativo':False}],t=Decimal('45.5'),v='pi-test')
    procesar(db_session)
    assert [a['tipo_variable'] for a in alertas(db_session,equipo)]==['SENSOR_FISICO_FALLIDO']
    eventos=h.evidencias(db_session,identificador,'HEARTBEAT')
    por_tipo={e['tipo_evento']:e for e in eventos}
    assert 'POSTCOMMIT_HEARTBEAT_SENSORES_COMPLETADO' in por_tipo
    assert por_tipo['POSTCOMMIT_HEARTBEAT_TEMPERATURA_FALLIDO']['accion_detallada']['error']=='UMBRAL_SOBRECALENTAMIENTO_NO_DISPONIBLE'
    assert por_tipo['POSTCOMMIT_HEARTBEAT_FIRMWARE_FALLIDO']['accion_detallada']['error']=='POLITICA_FIRMWARE_NO_DISPONIBLE'
    assert not any(e['tipo_evento'] in ('POSTCOMMIT_HEARTBEAT_TEMPERATURA_COMPLETADO','POSTCOMMIT_HEARTBEAT_FIRMWARE_COMPLETADO') for e in eventos)
    assert db_session.execute(text('SELECT temperatura_dispositivo FROM modulo3.heartbeats WHERE id_heartbeat=:id'),{'id':identificador}).scalar_one()==Decimal('45.50')


def test_http_ambos_campos_se_persisten_sin_politica(client,db_session,equipo):
    sensores=[{'sensor':'x','operativo':False}]
    response=enviar_http(client,equipo,sensores_operativos=sensores,temperatura_dispositivo=45.5)
    assert response.status_code==200,response.text
    assert response.json()['sensores_operativos']==sensores
    assert Decimal(response.json()['temperatura_dispositivo'])==Decimal('45.5')
    procesar(db_session)
    assert alertas(db_session,equipo)[0]['tipo_variable']=='SENSOR_FISICO_FALLIDO'


def test_recuperacion_tras_configuracion_y_cambio_sin_recrear_worker(db_session,equipo):
    # Solo se dobla la frontera M09/FW-06, pendiente en producción.
    politica=Mock()
    politica.obtener_umbrales_temperatura.side_effect=ServiceUnavailableError('CONFIGURACION_PENDIENTE','pendiente')
    procesador=construir_procesador(db_session.get_bind(),identidad=False,diagnostico_heartbeat=politica,reintento_seg=1)
    identificador=insertar_sql(db_session,equipo,t=Decimal(45))
    procesador.execute()
    assert not alertas(db_session,equipo)
    politica.obtener_umbrales_temperatura.side_effect=None
    politica.obtener_umbrales_temperatura.return_value=UmbralesTemperaturaDispositivo(Decimal(40))
    time.sleep(1.1)
    procesador.execute();procesador.execute()
    assert [a['tipo_variable'] for a in alertas(db_session,equipo)]==['SOBRECALENTAMIENTO']
    assert any(e['tipo_evento']=='POSTCOMMIT_HEARTBEAT_TEMPERATURA_COMPLETADO' for e in h.evidencias(db_session,identificador,'HEARTBEAT'))


def test_firmware_con_politica_inyectada_conserva_datos_y_no_duplica(db_session,equipo):
    politica=Mock()
    politica.comparar_firmware.return_value=ComparacionFirmware('minimo-de-prueba',True)
    insertar_sql(db_session,equipo,v='version-de-prueba')
    procesar(db_session,politica);procesar(db_session,politica)
    filas=alertas(db_session,equipo)
    assert len(filas)==1 and filas[0]['tipo_variable']=='FIRMWARE_DESACTUALIZADO'
    assert filas[0]['metadato_evento']['version_instalada']=='version-de-prueba'
    assert filas[0]['metadato_evento']['version_minima']=='minimo-de-prueba'


def test_fallo_al_guardar_alerta_revierte_etapa_y_permite_reintento(db_session,equipo,monkeypatch):
    from src.telemetry.infrastructure.repositories.alerta_repository import SqlAlchemyAlertaRepository
    identificador=insertar_sql(db_session,equipo,s=[{'sensor':'x','operativo':False}])
    original=SqlAlchemyAlertaRepository.guardar
    def fallar_despues_de_insertar(repo,alerta):
        resultado=original(repo,alerta)
        if alerta.id_dispositivo_ioit==equipo['device'] and alerta.tipo_variable=='SENSOR_FISICO_FALLIDO':
            raise RuntimeError('falla simulada antes del commit')
        return resultado
    with monkeypatch.context() as m:
        m.setattr(SqlAlchemyAlertaRepository,'guardar',fallar_despues_de_insertar)
        procesar(db_session)
    assert not alertas(db_session,equipo)
    eventos=h.evidencias(db_session,identificador,'HEARTBEAT')
    assert any(e['tipo_evento']=='POSTCOMMIT_HEARTBEAT_SENSORES_FALLIDO' for e in eventos)
    assert not any(e['tipo_evento']=='POSTCOMMIT_HEARTBEAT_SENSORES_COMPLETADO' for e in eventos)
    time.sleep(1.1)
    procesar(db_session)
    assert len(alertas(db_session,equipo))==1


def test_json_invalido_del_broker_queda_pendiente_sin_alerta_ficticia(db_session,equipo):
    identificador=insertar_sql(db_session,equipo,s=[{'sensor':'x','operativo':'false'}])
    procesar(db_session)
    assert not alertas(db_session,equipo)
    eventos=h.evidencias(db_session,identificador,'HEARTBEAT')
    assert any(e['tipo_evento']=='POSTCOMMIT_HEARTBEAT_SENSORES_FALLIDO' for e in eventos)
    assert not any(e['tipo_evento']=='POSTCOMMIT_HEARTBEAT_SENSORES_COMPLETADO' for e in eventos)


def test_heartbeat_sin_commit_no_es_visible_para_otro_procesador(integration_engine):
    with Session(integration_engine) as db:
        equipo=h.hardware(db)
    try:
        with integration_engine.connect() as conexion:
            tx=conexion.begin()
            with Session(bind=conexion,join_transaction_mode='create_savepoint') as db:
                identificador=insertar_sql(db,equipo,s=[{'sensor':'x','operativo':False}])
                with unidad_postcommit(integration_engine,identidad=False) as otro:
                    assert identificador not in otro.pendientes(EtapaPostcommit.HEARTBEAT_ESTADO,10000,1)
                    assert not otro.reclamar(EtapaPostcommit.HEARTBEAT_ESTADO,identificador)
            tx.rollback()
    finally:
        with integration_engine.begin() as c:
            c.execute(text('UPDATE modulo9.sensores SET es_activo=false WHERE id_sensores=:id'),{'id':equipo['sensor']})
            c.execute(text('UPDATE modulo9.dispositivos_iot SET es_activo=false WHERE id_dispositivo_iot=:id'),{'id':equipo['device']})

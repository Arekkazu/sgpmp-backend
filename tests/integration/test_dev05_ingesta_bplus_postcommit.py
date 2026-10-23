# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-42 RF-60: espera etapa RF60 y apagado inminente |
# | 2026-10-21 | Leandro | DEV-27 RF-60: regresion con politica persistida   |
# | 2026-10-21 | Leandro | DEV-41 RF-53/57: verifica etapa nueva sin duplicados |
# | 2026-10-22 | Leandro | DEV-44 RF-61: explicita asociacion RF-22 en fixture de ingesta |
"""PostgreSQL real; MQTT se representa por la misma función SQL, sin broker real."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import importlib
import pkgutil
from types import SimpleNamespace
from unittest.mock import Mock
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.orm import Session

from src.shared.database import get_db_sistema
from src.shared.error_handlers import register_error_handlers
from src.telemetry.domain.repositories.parametros_heartbeat_port import ParametrosHeartbeat, ParametrosComunicacionHeartbeat
from src.telemetry.domain.repositories.postcommit_port import EtapaPostcommit
from src.telemetry.infrastructure.repositories.ingesta_telemetria_repository import SqlAlchemyIngestaTelemetriaRepository
from src.telemetry.infrastructure.repositories.lectura_postcommit_repository import SqlAlchemyLecturaPostcommitRepository
from src.telemetry.infrastructure.repositories.postcommit_repository import unidad_postcommit
from src.telemetry.infrastructure.routers import telemetria_router, infraestructura_iot_router
from src.telemetry.infrastructure.workers.postcommit_worker import construir_procesador

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def modelos():
    for paquete in ('src.configuration.infrastructure.models', 'src.biological_assets.infrastructure.models',
                    'src.telemetry.infrastructure.models', 'src.identity_access.infrastructure.models'):
        mod = importlib.import_module(paquete)
        for item in pkgutil.iter_modules(mod.__path__, paquete + '.'):
            importlib.import_module(item.name)


def hardware(db):
    tag = uuid.uuid4().hex[:12]
    nombre = 'Desarrollo Bplus ' + ''.join(chr(97+int(c,16)) for c in tag)
    area = db.execute(text('''WITH finca AS (
        INSERT INTO modulo9.fincas(nombre,ubicacion,tamano_h,es_activo,fecha_creacion,fecha_actualizacion)
        VALUES (:nombre,'{}',10,true,now(),now()) RETURNING id_finca)
        INSERT INTO modulo9.infraestructuras(nombre,id_finca,superficie,es_activo,tipo)
        SELECT :nombre,id_finca,100,true,'Estanque' FROM finca RETURNING id_infraestructura
    '''), {'nombre':nombre}).scalar_one()
    device = db.execute(text('''INSERT INTO modulo9.dispositivos_iot(serial,descripcion,es_activo,fecha_creacion,id_infraestructura,id_tipo_dispositivo)
        VALUES (:serial,'DEV-05',true,now(),:area,3) RETURNING id_dispositivo_iot'''), {'serial':tag,'area':area}).scalar_one()
    sensor = db.execute(text('''INSERT INTO modulo9.sensores(id_dispositivo_iot,es_activo,nombre)
        VALUES (:device,true,'Sensor Bplus') RETURNING id_sensores'''), {'device':device}).scalar_one()
    db.execute(text('''INSERT INTO modulo9.sensores_areas_asociadas(id_sensor,id_dispositivo_iot,id_infraestructura,
        punto_instalacion,tiene_estado,fecha_asociacion,id_usuario)
        SELECT :sensor,:device,:area,'DEV05',true,now()-interval '1 day',min(id_usuario)
        FROM modulo1.usuarios'''),{'sensor':sensor,'device':device,'area':area})
    db.commit()
    return dict(device=device,sensor=sensor,area=area,serial=tag)


@pytest.fixture
def equipo(db_session):
    return hardware(db_session)


@pytest.fixture
def parametros_rf60(db_session):
    """Valores explícitos de prueba; no son defaults operativos aprobados."""
    from src.configuration.application.use_cases.configuracion_global.configurar_parametros_mlops_use_case import ConfigurarParametrosMLOpsUseCase
    from src.configuration.infrastructure.repositories.configuracion_global_repository import SqlAlchemyConfiguracionGlobalRepository
    from src.prediction.infrastructure.repositories.parametros_mlops_repository import SqlAlchemyParametrosMLOpsRepository
    usuario = db_session.execute(text('SELECT id_usuario FROM modulo1.usuarios ORDER BY id_usuario LIMIT 1')).scalar_one()
    db_session.execute(text('UPDATE modulo9.configuraciones_globales SET es_activo=false WHERE es_activo'))
    db_session.execute(text('''INSERT INTO modulo9.configuraciones_globales
        (frecuencia_muestreo,heartbeat,fecha_actualizacion,id_usuario,es_activo)
        VALUES (10,20,now(),:uid,true)'''), {'uid': usuario})
    db_session.commit()
    repo = SqlAlchemyParametrosMLOpsRepository(db_session)
    writer = ConfigurarParametrosMLOpsUseCase(db_session, repo, SqlAlchemyConfiguracionGlobalRepository(db_session))
    writer.execute({'intervalo_heartbeat_camara':120, 'intervalos_heartbeat_por_tipo':{'SENSOR':60},
                    'margen_tolerancia':300, 'tiempo_inactividad_extendida':3600}, usuario)
    return writer, usuario


@pytest.fixture
def client(db_session, headers_broker):
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(telemetria_router.router)
    app.include_router(infraestructura_iot_router.router)
    app.dependency_overrides[get_db_sistema] = lambda: db_session
    with TestClient(app, raise_server_exceptions=False, headers=headers_broker) as cliente:
        yield cliente


def payload(equipo, **cambios):
    return dict(dict(device_id=equipo['device'], sensor_id=equipo['sensor'], serial=equipo['serial'],
        tipo_variable='TEMPERATURA_AMBIENTAL', valor='22.5', unidad='°C',
        timestamp_captura=(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()), **cambios)


def sql_ingesta(db, equipo, captura=None, valor=Decimal('22.5'), unidad='°C', conectividad=True):
    ts = captura or datetime.now(timezone.utc)-timedelta(minutes=1)
    resultado = SqlAlchemyIngestaTelemetriaRepository(db).ingerir(dict(
        device_id=equipo['device'], sensor_id=equipo['sensor'], id_variable=9,
        categoria='AMBIENTAL', valor=valor, unidad=unidad, timestamp_captura=ts,
        timestamp_envio=ts, origen='TIEMPO_REAL', tipo_dato='CRUDO', valor_agregado=False,
        ventana_agregacion=None, latitud=None, longitud=None, nivel_bateria=None,
        calidad_senal_rssi=None, calidad_senal_snr=None, estado_conectividad=conectividad, metadatos={},
    ))
    db.commit()
    return resultado


def calidad(db, equipo, identificador, **cambios):
    datos = dict(id=identificador,sensor=equipo['sensor'],ia=True,nic=True,superada=None)
    datos.update(cambios)
    identificador = db.execute(text('''INSERT INTO modulo3.telemetria_calidad
        (id_telemetria,id_sensor,timestamp_evaluacion,indice_calidad,clasificacion_calidad,
         apto_para_ia,apto_para_nic41,flags_detectados,parametros_aplicados,estado_evaluacion,id_evaluacion_superada)
        VALUES (:id,:sensor,now(),100,'APTO',:ia,:nic,'{}','{}','VIGENTE',:superada)
        RETURNING id_evaluacion'''), datos).scalar_one()
    db.commit()
    return identificador


def procesador(db, **kwargs):
    return construir_procesador(db.get_bind(), identidad=False, **kwargs)


def evidencias(db, identificador, tipo='LECTURA'):
    return db.execute(text('''SELECT tipo_evento,resultado,accion_detallada,hash_integridad
        FROM modulo3.bitacora_auditoria_iot WHERE entidad_afectada_tipo=:tipo AND entidad_afectada_id=:id
        ORDER BY timestamp_registro,id_evento'''), {'tipo':tipo,'id':str(identificador)}).mappings().all()


@pytest.fixture
def parametros_rf62(db_session):
    """DEV-14: RF-62 lee sus parámetros de M04/M09 y falla si no están configurados."""
    from src.configuration.application.use_cases.configuracion_global.configurar_parametros_mlops_use_case import ConfigurarParametrosMLOpsUseCase
    from src.prediction.infrastructure.repositories.parametros_mlops_repository import SqlAlchemyParametrosMLOpsRepository
    usuario=db_session.execute(text('SELECT id_usuario FROM modulo1.usuarios ORDER BY id_usuario LIMIT 1')).scalar_one()
    ConfigurarParametrosMLOpsUseCase(db_session,SqlAlchemyParametrosMLOpsRepository(db_session)).execute(
        {'rf62_k':3,'rf62_m':5,'rf62_n':20,'rf62_umbral_drift':5,'rf62_p':3},usuario)
    if db_session.execute(text('SELECT count(*) FROM modulo9.configuraciones_globales WHERE es_activo')).scalar_one()==0:
        db_session.execute(text('''INSERT INTO modulo9.configuraciones_globales(frecuencia_muestreo,heartbeat,fecha_actualizacion,id_usuario,es_activo)
            VALUES (1,14,now(),:uid,true)'''),{'uid':usuario})
    db_session.commit()


def calibrar(db,equipo):
    usuario=db.execute(text('SELECT id_usuario FROM modulo1.usuarios ORDER BY id_usuario LIMIT 1')).scalar_one()
    db.execute(text('''INSERT INTO modulo9.calibraciones(id_sensor,id_dispositivo_iot,fecha_calibracion,valor_referencia,id_usuario)
        VALUES (:sensor,:device,now(),0,:usuario)'''),dict(sensor=equipo['sensor'],device=equipo['device'],usuario=usuario))
    db.commit()


@pytest.mark.parametrize('calibrado',[False,True])
def test_http_y_funcion_comun_persisten_misma_normalizacion_y_una_bitacora(client, db_session, equipo, calibrado):
    segundo = hardware(db_session)
    if calibrado:
        calibrar(db_session,equipo)
        calibrar(db_session,segundo)
    captura = datetime.now(timezone.utc)-timedelta(minutes=1)
    response = client.post('/iot/telemetria',json=payload(equipo,timestamp_captura=captura.isoformat()))
    assert response.status_code == 201, response.text
    directo = sql_ingesta(db_session,segundo,captura)
    ids = [response.json()['id_telemetria'], directo.id_telemetria]
    filas = db_session.execute(text('''SELECT valor_crudo,valor_ajustado,calibrado,estado_calidad,unidad_medida,
        timestamp_captura FROM modulo3.telemetrias WHERE id_telemetria=ANY(:ids) ORDER BY id_telemetria'''), {'ids':ids}).all()
    assert len(filas)==2 and filas[0]==filas[1]
    for identificador in ids:
        assert db_session.execute(text('SELECT count(*) FROM modulo3.bitacora_ingest WHERE id_telemetria=:id'),{'id':identificador}).scalar_one()==1


@pytest.mark.parametrize('cambio,estado', [({'unidad':'invalida'},400),
    ({'timestamp_captura':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()},400)])
def test_rechazos_funcionales_http_no_persisten(client, db_session, equipo, cambio, estado):
    response = client.post('/iot/telemetria',json=payload(equipo,**cambio))
    assert response.status_code==estado, response.text
    assert 'id_telemetria' not in response.json()
    assert db_session.execute(text('SELECT count(*) FROM modulo3.telemetrias WHERE id_sensor=:id'),{'id':equipo['sensor']}).scalar_one()==0


def test_batch_acepta_una_sola_vez_y_devuelve_duplicado(client, db_session, equipo):
    item = payload(equipo)
    response = client.post('/iot/telemetria/batch',json={'registros':[item,item,payload(equipo,unidad='invalida')]})
    assert response.status_code==200, response.text
    assert (response.json()['aceptados'],response.json()['duplicados'],response.json()['rechazados'])==(1,1,1)


def test_reinicio_completa_etapas_faltantes_aunque_ya_exista_calidad_y_no_muta_origen(db_session,equipo):
    identificador = sql_ingesta(db_session,equipo).id_telemetria
    calidad(db_session,equipo,identificador)
    antes = db_session.execute(text('SELECT to_jsonb(t) FROM modulo3.telemetrias t WHERE id_telemetria=:id'),{'id':identificador}).scalar_one()
    procesador(db_session).execute()
    procesador(db_session).execute()
    tipos = [x['tipo_evento'] for x in evidencias(db_session,identificador)]
    assert set(tipos)=={'POSTCOMMIT_RF61_COMPLETADO','POSTCOMMIT_RF62_COMPLETADO',
        'POSTCOMMIT_RF17_COMPLETADO','POSTCOMMIT_RF57_COMPLETADO',
        'POSTCOMMIT_RF60_COMPLETADO'}
    assert all(tipos.count(tipo)==1 for tipo in tipos)
    rf57=next(e for e in evidencias(db_session,identificador) if e['tipo_evento']=='POSTCOMMIT_RF57_COMPLETADO')
    assert rf57['accion_detallada']['resultado_etapa']['decision']=='EXCLUIDA_POR_CALIDAD'
    assert all(len(x['hash_integridad'])==64 for x in evidencias(db_session,identificador))
    from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import _calcular_hash
    from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import SqlAlchemyBitacoraAuditoriaIotRepository
    repo=SqlAlchemyBitacoraAuditoriaIotRepository(db_session)
    eventos,_=repo.listar(entidad_afectada_id=str(identificador),por_pagina=100)
    for evento in eventos:
        if evento.tipo_evento.startswith('POSTCOMMIT_'):
            assert evento.hash_integridad==_calcular_hash(evento)

    assert db_session.execute(text('SELECT count(*) FROM modulo3.vinculaciones_lecturas WHERE id_telemetria=:id'),{'id':identificador}).scalar_one()==1
    assert db_session.execute(text('SELECT to_jsonb(t) FROM modulo3.telemetrias t WHERE id_telemetria=:id'),{'id':identificador}).scalar_one()==antes


def test_fuente_oficial_excluye_evaluacion_superada_aun_si_dice_vigente(db_session,equipo):
    identificador=sql_ingesta(db_session,equipo).id_telemetria
    anterior=calidad(db_session,equipo,identificador,ia=False,nic=False)
    actual=calidad(db_session,equipo,identificador,superada=anterior)
    fila=SqlAlchemyLecturaPostcommitRepository(db_session).evaluacion_vigente(identificador)
    assert fila['id_evaluacion']==actual and fila['apto_para_ia'] and fila['apto_para_nic41']


def test_rf62_no_actualiza_telemetrias_ni_lee_flags_legacy(db_session,equipo,parametros_rf62):
    identificador=sql_ingesta(db_session,equipo).id_telemetria
    sentencias=[]
    conexion=db_session.get_bind()
    def capturar(_conn,_cursor,statement,_parameters,_context,_many): sentencias.append(statement.lower())
    event.listen(conexion,'before_cursor_execute',capturar)
    try:
        resultado=procesador(db_session).execute()
    finally:
        event.remove(conexion,'before_cursor_execute',capturar)
    assert any(x['tipo_evento']=='POSTCOMMIT_RF62_COMPLETADO' for x in evidencias(db_session,identificador)), resultado
    assert not any('update modulo3.telemetrias' in x for x in sentencias)
    assert not any('telemetrias.apto_para' in x for x in sentencias)


def test_falla_individual_no_impide_procesar_otra_lectura(db_session,equipo):
    ids=[sql_ingesta(db_session,equipo).id_telemetria,sql_ingesta(db_session,hardware(db_session)).id_telemetria]
    calidad(db_session,equipo,ids[0])
    p=procesador(db_session)
    accion=p.acciones[EtapaPostcommit.RF61]
    def fallar_uno(db, identificador):
        if identificador==ids[0]: raise RuntimeError('fallo controlado')
        accion(db,identificador)
    p.acciones[EtapaPostcommit.RF61]=fallar_uno
    p.execute()
    assert 'POSTCOMMIT_RF61_FALLIDO' in [x['tipo_evento'] for x in evidencias(db_session,ids[0])]
    assert 'POSTCOMMIT_RF61_COMPLETADO' in [x['tipo_evento'] for x in evidencias(db_session,ids[1])]


def test_falla_de_evidencia_revierte_efectos_aunque_caso_de_uso_haya_hecho_commit(db_session,equipo,monkeypatch):
    identificador=sql_ingesta(db_session,equipo).id_telemetria
    from src.telemetry.infrastructure.repositories.postcommit_repository import SqlAlchemyPostcommitRepository
    original=SqlAlchemyPostcommitRepository.registrar
    def fallo(self, etapa, identificador, error=None):
        if error is None: raise RuntimeError('falló evidencia')
        return original(self,etapa,identificador,error)
    monkeypatch.setattr(SqlAlchemyPostcommitRepository,'registrar',fallo)
    procesador(db_session).execute()
    assert db_session.execute(text('SELECT count(*) FROM modulo3.vinculaciones_lecturas WHERE id_telemetria=:id'),{'id':identificador}).scalar_one()==0
    assert not any(x['resultado']=='EXITOSO' for x in evidencias(db_session,identificador))


def guardar_heartbeat(db,equipo,**cambios):
    datos=dict(d=equipo['device'],buffer='A',bateria=None,rssi=None,fecha=datetime.now(timezone.utc)-timedelta(seconds=1))
    datos.update(cambios)
    identificador=db.execute(text('''INSERT INTO modulo3.heartbeats(id_dispositivo_iot,tipo_mensaje,
        nivel_bateria_pct,calidad_senal_rssi,estado_local_buffer,datos_pendientes_buffer,
        fecha_registro,fecha_recepcion,reloj_sincronizado)
        VALUES (:d,'HEARTBEAT',:bateria,:rssi,:buffer,2,:fecha,:fecha,true) RETURNING id_heartbeat'''),datos).scalar_one()
    db.commit()
    return identificador


@pytest.mark.parametrize('buffer',['A','L'])
def test_heartbeat_sql_buffer_persistido_se_recupera_y_no_se_duplica(db_session,equipo,buffer,parametros_rf60):
    identificador=guardar_heartbeat(db_session,equipo,buffer=buffer)
    procesador(db_session).execute()
    procesador(db_session).execute()
    # RF-60 Restricción 12: el contacto reciente tiene prioridad sobre el buffer.
    assert db_session.execute(text('SELECT estado_actual FROM modulo3.estados_dispositivos_iot WHERE id_dispositivo_iot=:id'),{'id':equipo['device']}).scalar_one()=='ACTIVO'
    assert len(evidencias(db_session,identificador,'HEARTBEAT'))==2
    assert db_session.execute(text('SELECT count(*) FROM modulo3.heartbeats WHERE id_dispositivo_iot=:id'),{'id':equipo['device']}).scalar_one()==1


def test_umbrales_ausentes_quedan_pendientes_sin_perder_estado_buffer(db_session,equipo,parametros_rf60):
    identificador=guardar_heartbeat(db_session,equipo,bateria=5,rssi=-110)
    resultado=procesador(db_session).execute()
    assert resultado['fallidos']>=1
    eventos=evidencias(db_session,identificador,'HEARTBEAT')
    assert {x['tipo_evento'] for x in eventos}=={'POSTCOMMIT_HEARTBEAT_ESTADO_COMPLETADO','POSTCOMMIT_HEARTBEAT_ALERTAS_FALLIDO'}
    assert 'PARAMETRO_CONFIGURACION_AUSENTE' in repr(eventos)
    assert db_session.execute(text('SELECT estado_actual FROM modulo3.estados_dispositivos_iot WHERE id_dispositivo_iot=:id'),{'id':equipo['device']}).scalar_one()=='ACTIVO'


def test_umbrales_inyectados_generan_alertas_sin_duplicados_ni_historial_inicial_extra(db_session,equipo,parametros_rf60):
    for _ in range(2): guardar_heartbeat(db_session,equipo,bateria=5,rssi=-110)
    parametros=SimpleNamespace(obtener=lambda: ParametrosHeartbeat(Decimal(10),Decimal(30),Decimal(-100)),
        obtener_comunicacion=lambda _id: ParametrosComunicacionHeartbeat(60,600,300,3600,'I'))
    procesador(db_session,parametros_heartbeat=parametros).execute()
    filas=db_session.execute(text('SELECT id_alerta,tipo_variable FROM modulo3.alertas WHERE id_dispositivo_ioit=:id'),{'id':equipo['device']}).all()
    assert len(filas)==2 and {x[1] for x in filas}=={'APAGADO_INMINENTE','SEÑAL_DEGRADADA'}
    for fila in filas:
        assert db_session.execute(text('SELECT count(*) FROM modulo3.historico_estados_alertas WHERE id_alerta=:id'),{'id':fila[0]}).scalar_one()==1


def test_bloqueo_de_fila_evita_doble_ejecucion_concurrente(integration_engine):
    # La fila se confirma en esta BD de pruebas: dos conexiones ven el mismo origen.
    with Session(integration_engine) as db:
        equipo=hardware(db)
        identificador=sql_ingesta(db,equipo).id_telemetria
    try:
        with unidad_postcommit(integration_engine,identidad=False) as primera:
            assert primera.reclamar(EtapaPostcommit.RF61,identificador)
            with ThreadPoolExecutor(max_workers=1) as pool:
                def intentar():
                    with unidad_postcommit(integration_engine,identidad=False) as otra:
                        return otra.reclamar(EtapaPostcommit.RF61,identificador)
                assert pool.submit(intentar).result(timeout=10) is False
            primera.registrar(EtapaPostcommit.RF61,identificador)
            primera.confirmar()
        with unidad_postcommit(integration_engine,identidad=False) as reinicio:
            assert not reinicio.reclamar(EtapaPostcommit.RF61,identificador)
    finally:
        # No se deshabilitan triggers de borrado. La BD efímera se destruye al final.
        with integration_engine.begin() as conn:
            conn.execute(text('UPDATE modulo9.sensores SET es_activo=false WHERE id_sensores=:id'),{'id':equipo['sensor']})
            conn.execute(text('UPDATE modulo9.dispositivos_iot SET es_activo=false WHERE id_dispositivo_iot=:id'),{'id':equipo['device']})


@pytest.mark.parametrize('bateria,rssi,esperadas', [
    (10,-100,{'BATERIA_CRITICA'}),
    (30,-101,{'BATERIA_BAJA','SEÑAL_DEGRADADA'}),
    (31,-100,set()),
])
def test_limites_de_alertas_son_los_parametros_del_puerto(db_session,equipo,bateria,rssi,esperadas,parametros_rf60):
    identificador=guardar_heartbeat(db_session,equipo,bateria=bateria,rssi=rssi,buffer='I')
    parametros=SimpleNamespace(obtener=lambda: ParametrosHeartbeat(Decimal(10),Decimal(30),Decimal(-100)),
        obtener_comunicacion=lambda _id: ParametrosComunicacionHeartbeat(60,600,300,3600,'I'))
    procesador(db_session,parametros_heartbeat=parametros).execute()
    assert {x['tipo_evento'] for x in evidencias(db_session,identificador,'HEARTBEAT')}=={
        'POSTCOMMIT_HEARTBEAT_ESTADO_COMPLETADO','POSTCOMMIT_HEARTBEAT_ALERTAS_COMPLETADO'}
    filas=db_session.execute(text('SELECT tipo_variable FROM modulo3.alertas WHERE id_dispositivo_ioit=:id'),{'id':equipo['device']}).scalars().all()
    assert set(filas)==esperadas


def test_origen_sin_commit_no_es_visible_para_procesador(integration_engine):
    with Session(integration_engine) as db:
        equipo=hardware(db)
    try:
        with integration_engine.connect() as conexion:
            tx=conexion.begin()
            with Session(bind=conexion,join_transaction_mode='create_savepoint') as db:
                identificador=sql_ingesta(db,equipo).id_telemetria
                with unidad_postcommit(integration_engine,identidad=False) as otro:
                    assert identificador not in otro.pendientes(EtapaPostcommit.RF61,10000,1)
                    assert not otro.reclamar(EtapaPostcommit.RF61,identificador)
            tx.rollback()
    finally:
        with integration_engine.begin() as conn:
            conn.execute(text('UPDATE modulo9.sensores SET es_activo=false WHERE id_sensores=:id'),{'id':equipo['sensor']})
            conn.execute(text('UPDATE modulo9.dispositivos_iot SET es_activo=false WHERE id_dispositivo_iot=:id'),{'id':equipo['device']})


def test_reintento_despues_de_fallo_recupera_solo_la_etapa_pendiente(db_session,equipo):
    from time import sleep
    identificador=sql_ingesta(db_session,equipo).id_telemetria
    calidad(db_session,equipo,identificador)
    p=procesador(db_session,reintento_seg=1)
    original=p.acciones[EtapaPostcommit.RF61]
    p.acciones[EtapaPostcommit.RF61]=Mock(side_effect=RuntimeError('indisponible'))
    p.execute()
    with unidad_postcommit(db_session.get_bind(),identidad=False) as u:
        assert identificador not in u.pendientes(EtapaPostcommit.RF61,1000,1)
    sleep(1.1)
    procesador(db_session,reintento_seg=1).execute()
    tipos=[x['tipo_evento'] for x in evidencias(db_session,identificador)]
    assert tipos.count('POSTCOMMIT_RF61_FALLIDO')==1
    assert tipos.count('POSTCOMMIT_RF61_COMPLETADO')==1
    assert tipos.count('POSTCOMMIT_RF17_COMPLETADO')==1
    assert tipos.count('POSTCOMMIT_RF62_COMPLETADO')==1


def test_heartbeat_http_conserva_autenticacion_y_se_procesa_sin_reinsertar(client,db_session,equipo,parametros_rf60):
    body={'device_id':equipo['device'],'serial':equipo['serial'],'tipo_mensaje':'HEARTBEAT','estado_local_buffer':'A',
          'fecha_registro':(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()}
    denegado=client.post('/iot/heartbeat',json=dict(body,serial='incorrecto'))
    assert denegado.status_code==401,denegado.text
    response=client.post('/iot/heartbeat',json=body)
    assert response.status_code==200,response.text
    identificador=response.json()['id_heartbeat']
    procesador(db_session).execute()
    assert {x['tipo_evento'] for x in evidencias(db_session,identificador,'HEARTBEAT')}=={
        'POSTCOMMIT_HEARTBEAT_ESTADO_COMPLETADO','POSTCOMMIT_HEARTBEAT_ALERTAS_COMPLETADO'}
    assert db_session.execute(text('SELECT count(*) FROM modulo3.heartbeats WHERE id_dispositivo_iot=:id'),{'id':equipo['device']}).scalar_one()==1


def test_cache_se_restaura_con_captura_mayor_y_no_verde_sin_umbral(db_session,equipo):
    calibrar(db_session,equipo)
    ts=datetime.now(timezone.utc)-timedelta(minutes=1)
    actual=sql_ingesta(db_session,equipo,ts,Decimal('22')).id_telemetria
    procesador(db_session).execute()
    vieja=sql_ingesta(db_session,equipo,ts-timedelta(minutes=1),Decimal('21'),conectividad=False).id_telemetria
    procesador(db_session).execute()
    fila=db_session.execute(text('''SELECT ultimo_timestamp_captura,ultimo_valor,estado_semaforo,estado_conectividad FROM modulo3.estados_actuales_sensores
        WHERE id_sensor=:id'''),{'id':equipo['sensor']}).one()
    assert fila[0]==ts and fila[1]==Decimal('22') and fila[2]=='GRIS' and fila[3]=='ACTIVO'
    assert any(x['tipo_evento']=='POSTCOMMIT_RF17_COMPLETADO' for x in evidencias(db_session,vieja))


def test_rf53_sigue_rechazando_updates_y_delete(db_session,equipo):
    from sqlalchemy.exc import DBAPIError
    identificador=sql_ingesta(db_session,equipo).id_telemetria
    for sentencia in ('UPDATE modulo3.telemetrias SET valor_crudo=0 WHERE id_telemetria=:id',
                      'DELETE FROM modulo3.telemetrias WHERE id_telemetria=:id'):
        with pytest.raises(DBAPIError) as error:
            with db_session.begin_nested(): db_session.execute(text(sentencia),{'id':identificador})
        assert error.value.orig.pgcode=='P0002'


@pytest.mark.parametrize('estado,severidad,esperado', [
    ('ACTIVO',None,'VERDE'), ('ACTIVO','MODERADO','AMARILLO'),
    ('ACTIVO','CRITICO','ROJO'), ('SIN_SEÑAL','CRITICO','GRIS'),
])
def test_prioridades_semaforo_respetan_estado_operativo_y_alertas(db_session,equipo,estado,severidad,esperado):
    calibrar(db_session,equipo)
    identificador=sql_ingesta(db_session,equipo).id_telemetria
    guardar_heartbeat(db_session,equipo,buffer='I')
    if severidad:
        from src.telemetry.domain.entities.alerta import Alerta
        from src.telemetry.infrastructure.repositories.alerta_repository import SqlAlchemyAlertaRepository
        ahora=datetime.now(timezone.utc)
        SqlAlchemyAlertaRepository(db_session).guardar(Alerta(
            tipo_alerta='TECNICA',severidad=severidad,estado_alerta='ACTIVA',origen_evento='BACKEND',
            tipo_variable='TEMPERATURA_AMBIENTAL',id_sensor=equipo['sensor'],id_dispositivo_ioit=equipo['device'],
            id_infraestructura=equipo['area'],fecha_evento=ahora,fecha_generacion=ahora))
    if estado=='SIN_SEÑAL':
        db_session.execute(text("UPDATE modulo3.estados_dispositivos_iot SET estado_actual='SIN_SEÑAL',causa_primaria='FALLO_CONECTIVIDAD' WHERE id_dispositivo_iot=:id"),{'id':equipo['device']})
    repo=SqlAlchemyLecturaPostcommitRepository(db_session)
    repo.aplicar_prioridades(repo.obtener_por_id(identificador),'VERDE')
    assert db_session.execute(text('SELECT estado_semaforo FROM modulo3.estados_actuales_sensores WHERE id_sensor=:id'),{'id':equipo['sensor']}).scalar_one()==esperado


def test_heartbeat_no_saca_dispositivo_de_mantenimiento(db_session,equipo,parametros_rf60):
    guardar_heartbeat(db_session,equipo,buffer='I')
    db_session.execute(text("UPDATE modulo3.estados_dispositivos_iot SET estado_actual='EN_MANTENIMIENTO' WHERE id_dispositivo_iot=:id"),{'id':equipo['device']})
    db_session.commit()
    identificador=guardar_heartbeat(db_session,equipo,buffer='A')
    procesador(db_session).execute()
    assert db_session.execute(text('SELECT estado_actual FROM modulo3.estados_dispositivos_iot WHERE id_dispositivo_iot=:id'),{'id':equipo['device']}).scalar_one()=='EN_MANTENIMIENTO'
    assert any(x['tipo_evento']=='POSTCOMMIT_HEARTBEAT_ESTADO_COMPLETADO' for x in evidencias(db_session,identificador,'HEARTBEAT'))


def test_contrato_db02_calibracion_usa_ganancia_y_offset_de_rf24(db_session,equipo):
    # El valor de referencia no es el offset: con 25 de referencia, 2x+1 debe dar 21.
    usuario=db_session.execute(text('SELECT id_usuario FROM modulo1.usuarios ORDER BY id_usuario LIMIT 1')).scalar_one()
    db_session.execute(text('''INSERT INTO modulo9.calibraciones(id_sensor,id_dispositivo_iot,fecha_calibracion,
        valor_referencia,ganancia,offset_calibracion,id_usuario) VALUES (:s,:d,now(),25,2,1,:u)'''),
        dict(s=equipo['sensor'],d=equipo['device'],u=usuario))
    db_session.commit()
    identificador=sql_ingesta(db_session,equipo,valor=Decimal('10')).id_telemetria
    assert db_session.execute(text('SELECT valor_ajustado FROM modulo3.telemetrias WHERE id_telemetria=:id'),
                              {'id':identificador}).scalar_one()==Decimal('21')


def test_contrato_db02_sin_calibracion_deja_valor_ajustado_null(db_session,equipo):
    identificador=sql_ingesta(db_session,equipo).id_telemetria
    assert db_session.execute(text('SELECT valor_ajustado FROM modulo3.telemetrias WHERE id_telemetria=:id'),{'id':identificador}).scalar_one() is None


def test_contrato_db02_rechazo_sql_conserva_bitacora(db_session,equipo):
    resultado=sql_ingesta(db_session,equipo,unidad='incorrecta')
    assert resultado.id_telemetria is None
    assert db_session.execute(text('''SELECT count(*) FROM modulo3.bitacora_ingest
        WHERE id_sensor=:id AND estado_calidad='ERROR_UNIDAD' '''),{'id':equipo['sensor']}).scalar_one()==1


def test_serie_20_lecturas_evalua_rf62_cuando_dev02_esta_integrado(db_session,equipo,parametros_rf62):
    from src.telemetry.domain.repositories.telemetria_repository import TelemetriaRepository
    if hasattr(TelemetriaRepository,'actualizar_flags_aptitud'):
        pytest.skip('Requiere DEV-02 integrado; esta rama no duplica su corrección.')
    calibrar(db_session,equipo)
    inicio=datetime.now(timezone.utc)-timedelta(minutes=30)
    ids=[sql_ingesta(db_session,equipo,inicio+timedelta(minutes=i),Decimal(20)+Decimal(i%5)/10).id_telemetria for i in range(21)]
    antes=db_session.execute(text('SELECT jsonb_agg(to_jsonb(t) ORDER BY id_telemetria) FROM modulo3.telemetrias t WHERE id_sensor=:id'),{'id':equipo['sensor']}).scalar_one()
    procesador(db_session).execute()
    evaluacion=SqlAlchemyLecturaPostcommitRepository(db_session).evaluacion_vigente(ids[-1])
    assert evaluacion is not None and evaluacion['apto_para_ia'] and evaluacion['apto_para_nic41']
    assert db_session.execute(text('SELECT jsonb_agg(to_jsonb(t) ORDER BY id_telemetria) FROM modulo3.telemetrias t WHERE id_sensor=:id'),{'id':equipo['sensor']}).scalar_one()==antes
    assert any(x['tipo_evento']=='POSTCOMMIT_RF62_COMPLETADO' for x in evidencias(db_session,ids[-1]))

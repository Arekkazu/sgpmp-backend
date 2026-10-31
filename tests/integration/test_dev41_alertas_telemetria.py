# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-41 RF-53/57: integra SQL broker, worker y concurrencia |
# | 2026-10-23 | Arekkazu | INTEG RFC-012..016 DEV-44: el activo del fixture tiene historial de ubicacion |
# | 2026-10-31 | Arekkazu | PR-891 RF-23: config global de respaldo respeta el piso de 5 min |
"""Frontera SQL real del broker B+; no hay broker MQTT externo en estas pruebas."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import time
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.telemetry.domain.repositories.postcommit_port import EtapaPostcommit
from src.telemetry.infrastructure.repositories.ingesta_telemetria_repository import SqlAlchemyIngestaTelemetriaRepository
from src.telemetry.infrastructure.repositories.postcommit_repository import SqlAlchemyPostcommitRepository
from src.telemetry.infrastructure.workers.postcommit_worker import construir_procesador
from src.telemetry.infrastructure.repositories.alerta_repository import SqlAlchemyAlertaRepository
from src.telemetry.application.use_cases.alertas.generar_alerta_use_case import GenararAlertaUseCase
from src.telemetry.infrastructure.dto.procesar_evento_alerta_dto import ProcesarEventoAlertaDTO
from src.telemetry.infrastructure.repositories.historico_estado_alerta_repository import SqlAlchemyHistoricoEstadoAlertaRepository
from src.telemetry.infrastructure.repositories.regla_alerta_repository import SqlAlchemyReglaAlertaRepository
from src.telemetry.infrastructure.adapters.parametros_alertas_mlops_adapter import ParametrosAlertasMLOpsAdapter
from src.prediction.infrastructure.repositories.parametros_mlops_repository import SqlAlchemyParametrosMLOpsRepository
from src.configuration.application.use_cases.configuracion_global.configurar_parametros_mlops_use_case import ConfigurarParametrosMLOpsUseCase
from src.shared.database import declarar_identidad

_spec = importlib.util.spec_from_file_location('dev41_base',Path(__file__).with_name('test_dev05_ingesta_bplus_postcommit.py'))
h = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h)
modelos = h.modelos
client = h.client
pytestmark = pytest.mark.integration


def preparar(db, *, calibrado=True, variable=9, unidad='°C', categoria='AMBIENTAL'):
    equipo = h.hardware(db)
    usuario, rol = db.execute(text('SELECT u.id_usuario,r.nombre_rol FROM modulo1.usuarios u JOIN modulo1.roles r USING(id_rol) ORDER BY u.id_usuario LIMIT 1')).one()
    declarar_identidad(db,usuario,rol)
    tag = ''.join(chr(97+int(c,16)) for c in uuid.uuid4().hex[:12])
    especie = db.execute(text('''INSERT INTO modulo9.especies(nombre,descripcion,fecha_creacion,es_activo)
        VALUES(:nombre,'Fixture DEV-41',now(),true) RETURNING id_especie'''), {'nombre':'Especie '+tag}).scalar_one()
    db.execute(text("INSERT INTO modulo2.estados_activos_biologicos(id_estado_activo_biologico,nombre) VALUES(1,'ACTIVO') ON CONFLICT DO NOTHING"))
    activo = db.execute(text('''INSERT INTO modulo2.activos_biologicos
        (id_especie,identificador,id_infraestructura,tipo,fecha_inicio_ciclo,id_estado,
         descripcion,origen_financiero,costo_adquisicion,atributos_dinamicos,id_usuario,
         fecha_creacion,soporte_documental,detalles_procedencia)
        VALUES(:especie,:codigo,:area,'INDIVIDUAL',current_date,1,'DEV-41','compra',100,'{}',:uid,now()-interval '1 day','doc','')
        RETURNING id_activo_biologico'''), {'especie':especie,'codigo':'DEV41-'+tag,
        'area':equipo['area'],'uid':usuario}).scalar_one()
    # DEV-44: RF-61 ubica al activo por su historial a la hora de captura; el
    # activo tiene que estar en el área antes de las lecturas de la prueba.
    # (el registro de M02 crea esta fila en el repositorio; el INSERT directo de la prueba no).
    db.execute(text('''INSERT INTO modulo2.historial_infraestructura_activo
        (id_activo_biologico,id_infraestructura,fecha_inicio,id_usuario_registro)
        VALUES(:a,:area,now()-interval '1 day',:uid)'''), {'a':activo,'area':equipo['area'],'uid':usuario})
    umbral = db.execute(text('''INSERT INTO modulo9.umbrales_ambientales
        (id_especie,id_variable_ambiental,unidad_medida,valor_min,valor_max,es_activo,fecha_actualizacion,id_usuario)
        VALUES(:e,:v,:u,20,50,true,now(),:uid) RETURNING id_umbral_ambiental'''),
        {'e':especie,'v':variable,'u':unidad,'uid':usuario}).scalar_one()
    for nivel,a,b in [('normal',20,30),('precaucion',31,35),('critico',36,50)]:
        db.execute(text('''INSERT INTO modulo9.niveles_alerta_ambientales
            (id_umbral_ambiental,nivel,limite_inferior,limite_superior) VALUES(:id,:n,:a,:b)'''),
            {'id':umbral,'n':nivel,'a':a,'b':b})
    ConfigurarParametrosMLOpsUseCase(db,SqlAlchemyParametrosMLOpsRepository(db)).execute(
        {'rf62_k':3,'rf62_m':5,'rf62_n':20,'rf62_umbral_drift':5,'rf62_p':3},usuario)
    if db.execute(text('SELECT count(*) FROM modulo9.configuraciones_globales WHERE es_activo')).scalar_one()==0:
        db.execute(text('''INSERT INTO modulo9.configuraciones_globales
            (frecuencia_muestreo,heartbeat,fecha_actualizacion,id_usuario,es_activo)
            VALUES(5,14,now(),:uid,true)'''), {'uid':usuario})
    db.commit()
    if calibrado:
        h.calibrar(db,equipo)
    return equipo | dict(especie=especie,activo=activo,umbral=umbral,variable=variable,unidad=unidad,categoria=categoria)


@pytest.fixture
def contexto(db_session):
    return preparar(db_session)


def ingresar(db, ctx, valor=40, captura=None):
    ts = captura or datetime.now(timezone.utc)-timedelta(minutes=1)
    resultado = SqlAlchemyIngestaTelemetriaRepository(db).ingerir(dict(device_id=ctx['device'],
        sensor_id=ctx['sensor'],id_variable=ctx['variable'],categoria=ctx['categoria'],valor=Decimal(str(valor)),
        unidad=ctx['unidad'],timestamp_captura=ts,timestamp_envio=ts,origen='TIEMPO_REAL',tipo_dato='CRUDO',
        valor_agregado=False,ventana_agregacion=None,latitud=None,longitud=None,nivel_bateria=None,
        calidad_senal_rssi=None,calidad_senal_snr=None,estado_conectividad=True,metadatos={}))
    db.commit()
    return resultado


def alertas(db,ctx):
    return db.execute(text('''SELECT id_alerta,estado_alerta,severidad,frecuencia_evento,
        origen_evento,id_telemetria,id_sensor,id_dispositivo_ioit,id_infraestructura,metadato_evento
        FROM modulo3.alertas WHERE id_sensor=:s ORDER BY id_alerta'''), {'s':ctx['sensor']}).mappings().all()


def worker(db):
    return construir_procesador(db.get_bind(),identidad=False,reintento_seg=1,limite=10000)


def resultado_etapa(db, identificador):
    eventos = h.evidencias(db,identificador)
    return next(e['accion_detallada']['resultado_etapa'] for e in eventos if e['tipo_evento']=='POSTCOMMIT_RF57_COMPLETADO')


@pytest.mark.parametrize('valor,espera',[('22',0),('33',0),('40',1)])
def test_bandas_reales_rf17_desde_frontera_sql_broker(db_session,contexto,valor,espera):
    lectura = ingresar(db_session,contexto,valor)
    assert lectura.estado_calidad=='LECTURA_VALIDA'
    assert not alertas(db_session,contexto)
    worker(db_session).execute()
    assert len(alertas(db_session,contexto))==espera
    assert resultado_etapa(db_session,lectura.id_telemetria)['decision']==('CREADA' if espera else 'NO_CRITICA')


def test_dos_lecturas_mqtt_sql_consolidan_y_reintentos_no_incrementan(db_session,contexto):
    primero = ingresar(db_session,contexto)
    antes = db_session.execute(text('SELECT to_jsonb(t) FROM modulo3.telemetrias t WHERE id_telemetria=:id'), {'id':primero.id_telemetria}).scalar_one()
    p = worker(db_session)
    p.execute()
    a = alertas(db_session,contexto)[0]
    assert (a['estado_alerta'],a['severidad'],a['frecuencia_evento'],a['origen_evento'])==('ACTIVA','CRITICO',1,'BACKEND')
    assert a['id_telemetria']==primero.id_telemetria and a['id_dispositivo_ioit']==contexto['device']
    assert a['metadato_evento']['id_umbral_ambiental']==contexto['umbral']
    segundo = ingresar(db_session,contexto,41)
    p.execute()
    p.execute()
    filas = alertas(db_session,contexto)
    assert len(filas)==1 and filas[0]['frecuencia_evento']==2
    assert resultado_etapa(db_session,segundo.id_telemetria)['id_alerta']==a['id_alerta']
    assert resultado_etapa(db_session,segundo.id_telemetria)['decision']=='CONSOLIDADA'
    assert resultado_etapa(db_session,segundo.id_telemetria)['contexto_rf17']['valor_evaluado']=='41.0000'
    assert filas[0]['metadato_evento']['valor_evaluado']=='40.0000'
    assert db_session.execute(text('SELECT count(*) FROM modulo3.historico_estados_alertas WHERE id_alerta=:id'), {'id':a['id_alerta']}).scalar_one()==1
    assert db_session.execute(text('SELECT to_jsonb(t) FROM modulo3.telemetrias t WHERE id_telemetria=:id'), {'id':primero.id_telemetria}).scalar_one()==antes


def test_redelivery_sql_idempotente_no_suma_frecuencia(db_session,contexto):
    captura = datetime.now(timezone.utc)-timedelta(minutes=2)
    primero = ingresar(db_session,contexto,captura=captura)
    p = worker(db_session)
    p.execute()
    repetido = ingresar(db_session,contexto,captura=captura)
    assert repetido.id_telemetria is None and 'ERROR_DUPLICADO' in repetido.mensaje
    p.execute()
    assert alertas(db_session,contexto)[0]['frecuencia_evento']==1
    assert resultado_etapa(db_session,primero.id_telemetria)['decision']=='CREADA'


def test_lectura_critica_tardia_no_toma_color_de_la_ultima_normal(db_session,contexto):
    critico = ingresar(db_session,contexto,40,datetime.now(timezone.utc)-timedelta(minutes=5))
    normal = ingresar(db_session,contexto,22)
    worker(db_session).execute()
    assert len(alertas(db_session,contexto))==1
    assert alertas(db_session,contexto)[0]['id_telemetria']==critico.id_telemetria
    assert resultado_etapa(db_session,normal.id_telemetria)['decision']=='NO_CRITICA'


def test_error_calibracion_no_genera_alerta(db_session):
    ctx = preparar(db_session,calibrado=False)
    lectura = ingresar(db_session,ctx)
    assert lectura.estado_calidad=='ERROR_CALIBRACION'
    worker(db_session).execute()
    assert not alertas(db_session,ctx)
    assert resultado_etapa(db_session,lectura.id_telemetria)['decision']=='EXCLUIDA_POR_CALIDAD'


def test_sin_umbral_activo_conserva_ausencia_clasificacion_rf17(db_session,contexto):
    db_session.execute(text('UPDATE modulo9.umbrales_ambientales SET es_activo=false WHERE id_umbral_ambiental=:id'), {'id':contexto['umbral']})
    db_session.commit()
    lectura = ingresar(db_session,contexto)
    worker(db_session).execute()
    assert not alertas(db_session,contexto)
    assert resultado_etapa(db_session,lectura.id_telemetria)['decision']=='SIN_CLASIFICACION_RF17'


@pytest.mark.parametrize('fallo',['alerta','evidencia'])
def test_fallo_postcommit_revierte_alerta_sin_perder_telemetria(db_session,contexto,monkeypatch,fallo):
    lectura = ingresar(db_session,contexto)
    if fallo=='alerta':
        original = SqlAlchemyAlertaRepository.guardar
        def fallar(self,alerta):
            original(self,alerta)
            raise RuntimeError('Fallo de prueba después de insertar')
        objeto,nombre,reemplazo = SqlAlchemyAlertaRepository,'guardar',fallar
    else:
        original = SqlAlchemyPostcommitRepository.registrar
        def fallar(self,etapa,identificador,error=None,**kw):
            if etapa is EtapaPostcommit.RF57 and error is None:
                raise RuntimeError('Fallo de evidencia de prueba')
            return original(self,etapa,identificador,error,**kw)
        objeto,nombre,reemplazo = SqlAlchemyPostcommitRepository,'registrar',fallar
    p = worker(db_session)
    with monkeypatch.context() as m:
        m.setattr(objeto,nombre,reemplazo)
        p.execute()
    assert not alertas(db_session,contexto)
    assert db_session.execute(text('SELECT count(*) FROM modulo3.telemetrias WHERE id_telemetria=:id'), {'id':lectura.id_telemetria}).scalar_one()==1
    assert any(e['tipo_evento']=='POSTCOMMIT_RF57_FALLIDO' for e in h.evidencias(db_session,lectura.id_telemetria))
    time.sleep(1.1)
    p.execute()
    p.execute()
    assert alertas(db_session,contexto)[0]['frecuencia_evento']==1


def test_fallo_consolidacion_no_incrementa_dos_veces(db_session,contexto,monkeypatch):
    ingresar(db_session,contexto)
    p = worker(db_session)
    p.execute()
    segunda = ingresar(db_session,contexto,41)
    original = SqlAlchemyAlertaRepository.actualizar_deduplicacion
    def fallar(self,*args,**kw):
        original(self,*args,**kw)
        raise RuntimeError('Fallo de consolidación de prueba')
    with monkeypatch.context() as m:
        m.setattr(SqlAlchemyAlertaRepository,'actualizar_deduplicacion',fallar)
        p.execute()
    assert alertas(db_session,contexto)[0]['frecuencia_evento']==1
    time.sleep(1.1)
    p.execute()
    p.execute()
    assert alertas(db_session,contexto)[0]['frecuencia_evento']==2
    assert resultado_etapa(db_session,segunda.id_telemetria)['decision']=='CONSOLIDADA'


def generador(db):
    return GenararAlertaUseCase(db,SqlAlchemyAlertaRepository(db),SqlAlchemyHistoricoEstadoAlertaRepository(db),
        SqlAlchemyReglaAlertaRepository(db),ParametrosAlertasMLOpsAdapter(SqlAlchemyParametrosMLOpsRepository(db)))


def evento(ctx, *, origen='EDGE', codigo='TEMPERATURA_AMBIENTAL'):
    return ProcesarEventoAlertaDTO(device_id=ctx['device'],sensor_id=ctx['sensor'],serial=ctx['serial'],
        tipo_variable=codigo,valor=40,unidad=ctx['unidad'],timestamp_evento=datetime.now(timezone.utc),
        estado_dato='LECTURA_VALIDA',severidad_edge='CRITICO',origen_evento=origen)


@pytest.mark.parametrize('variable,unidad,categoria,codigo',[(9,'°C','AMBIENTAL','TEMPERATURA_AMBIENTAL'),
    (8,'µS/cm','HIDRICA','CONDUCTIVIDAD_ELECTRICA')])
def test_evento_edge_equivalente_compartido_con_alerta_backend(db_session,variable,unidad,categoria,codigo):
    ctx = preparar(db_session,variable=variable,unidad=unidad,categoria=categoria)
    ingresar(db_session,ctx)
    worker(db_session).execute()
    resultado = generador(db_session).execute(evento(ctx,codigo=codigo),id_dispositivo_ioit=ctx['device'],
        id_infraestructura=ctx['area'])
    assert resultado.es_duplicado
    assert len(alertas(db_session,ctx))==1 and alertas(db_session,ctx)[0]['frecuencia_evento']==2


def test_fuera_de_ventana_conserva_contrato_rf57(db_session,contexto,monkeypatch):
    import src.telemetry.application.use_cases.alertas.generar_alerta_use_case as modulo
    pasado = datetime.now(timezone.utc)-timedelta(minutes=31)
    with monkeypatch.context() as m:
        m.setattr(modulo,'datetime',SimpleNamespace(now=lambda _tz:pasado))
        generador(db_session).execute(evento(contexto))
    ingresar(db_session,contexto)
    worker(db_session).execute()
    assert [a['frecuencia_evento'] for a in alertas(db_session,contexto)]==[1,1]


def test_http_y_batch_conservan_ingesta_y_generan_solo_tras_worker(client,db_session,contexto):
    primera = h.payload(contexto,valor='40')
    response = client.post('/iot/telemetria',json=primera)
    assert response.status_code==201,response.text
    segunda = h.payload(contexto,valor='41',timestamp_captura=(datetime.now(timezone.utc)-timedelta(seconds=30)).isoformat())
    lote = client.post('/iot/telemetria/batch',json={'registros':[primera,segunda]})
    assert lote.status_code==200 and (lote.json()['aceptados'],lote.json()['duplicados'])==(1,1),lote.text
    assert not alertas(db_session,contexto)
    worker(db_session).execute()
    assert len(alertas(db_session,contexto))==1 and alertas(db_session,contexto)[0]['frecuencia_evento']==2


def test_endpoint_edge_existente_consolida_con_condicion_backend(client,db_session,contexto):
    from src.telemetry.infrastructure.routers.evento_edge_router import router
    client.app.include_router(router)
    ingresar(db_session,contexto)
    worker(db_session).execute()
    ahora = datetime.now(timezone.utc).isoformat()
    respuesta = client.post('/iot/eventos-edge',json={
        'device_id':contexto['device'],'sensor_id':contexto['sensor'],'serial':contexto['serial'],
        'clasificacion_rf55':'DESVIACION_SIMPLE','severidad':'CRITICO',
        'variables_involucradas':[{'tipo_variable':'TEMPERATURA_AMBIENTAL','valor':41,'unidad':'°C'}],
        'timestamp_captura':ahora,'timestamp_procesamiento_edge':ahora,'estado_conectividad':True})
    assert respuesta.status_code==201,respuesta.text
    assert respuesta.json()['id_evento_edge_computing']
    assert len(alertas(db_session,contexto))==1 and alertas(db_session,contexto)[0]['frecuencia_evento']==2


@pytest.mark.parametrize('confirmar',[False,True])
def test_telemetria_no_confirmada_no_es_visible_para_worker(integration_engine,confirmar):
    with Session(integration_engine) as db:
        ctx = preparar(db)
    with integration_engine.connect() as conexion:
        tx = conexion.begin()
        with Session(bind=conexion,join_transaction_mode='create_savepoint') as db:
            lectura = ingresar(db,ctx)
            construir_procesador(integration_engine,identidad=False,limite=10000).execute()
            with Session(integration_engine) as verificador:
                assert not alertas(verificador,ctx)
        if confirmar:
            tx.commit()
        else:
            tx.rollback()
    construir_procesador(integration_engine,identidad=False,limite=10000).execute()
    with Session(integration_engine) as verificador:
        if confirmar:
            assert alertas(verificador,ctx)[0]['id_telemetria']==lectura.id_telemetria
        else:
            assert not alertas(verificador,ctx)


def test_fallo_rf62_no_permite_adelantar_alertas_y_luego_recupera(db_session,contexto,monkeypatch):
    from src.telemetry.application.use_cases.calidad.evaluar_calidad_telemetria_use_case import EvaluarCalidadTelemetriaUseCase
    lectura = ingresar(db_session,contexto)
    def fallar(*args,**kw):
        raise RuntimeError('Calidad temporalmente no disponible')
    p = worker(db_session)
    with monkeypatch.context() as m:
        m.setattr(EvaluarCalidadTelemetriaUseCase,'execute',fallar)
        p.execute()
    assert not alertas(db_session,contexto)
    assert not any(e['tipo_evento'].startswith('POSTCOMMIT_RF57_') for e in h.evidencias(db_session,lectura.id_telemetria))
    time.sleep(1.1)
    p.execute()
    p.execute()
    assert alertas(db_session,contexto)[0]['frecuencia_evento']==1


def test_dos_workers_concurrentes_no_duplican_condicion_ni_frecuencia(integration_engine):
    with Session(integration_engine) as db:
        ctx = preparar(db)
        ingresar(db,ctx,40)
        ingresar(db,ctx,41)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(construir_procesador(integration_engine,identidad=False,limite=10000).execute) for _ in range(2)]
        for f in futures:
            f.result(timeout=35)
    construir_procesador(integration_engine,identidad=False,limite=10000).execute()
    with Session(integration_engine) as db:
        assert len(alertas(db,ctx))==1 and alertas(db,ctx)[0]['frecuencia_evento']==2


def test_origenes_concurrentes_comparten_bloqueo_rf57(integration_engine):
    with Session(integration_engine) as db:
        ctx = preparar(db)
    def procesar(origen):
        with Session(integration_engine) as db:
            return generador(db).execute(evento(ctx,origen=origen)).id_alerta
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(procesar,['EDGE','BACKEND']))
    assert ids[0]==ids[1]
    with Session(integration_engine) as db:
        assert len(alertas(db,ctx))==1 and alertas(db,ctx)[0]['frecuencia_evento']==2

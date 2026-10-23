# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-44 RF-61: verifica DB-13, contexto, avisos y traslados reales |
"""PostgreSQL aislado. Avisos usan dobles explicitos, sin acreditar entrega real."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
import subprocess
import sys
import uuid
import pytest
from sqlalchemy import create_engine,text
from sqlalchemy.orm import Session

from src.shared.errors import BusinessRuleError,NotFoundError,ServiceUnavailableError
from src.telemetry.infrastructure.adapters.activo_biologico_m02_adapter import ActivoBiologicoM02Adapter
from src.telemetry.infrastructure.adapters.vinculacion_traslado_m03_adapter import VinculacionTrasladoM03Adapter
from src.telemetry.infrastructure.adapters.destinatarios_vinculacion_m01_adapter import DestinatariosVinculacionM01Adapter
from src.telemetry.infrastructure.repositories.vinculacion_lectura_repository import SqlAlchemyVinculacionLecturaRepository
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import SqlAlchemyBitacoraAuditoriaIotRepository
from src.telemetry.infrastructure.repositories.postcommit_repository import unidad_postcommit
from src.telemetry.infrastructure.workers.postcommit_worker import construir_procesador
from src.telemetry.domain.repositories.postcommit_port import EtapaPostcommit
from src.telemetry.application.use_cases.infraestructura.vincular_lectura_activo_use_case import VincularLecturaActivoUseCase
from src.telemetry.application.use_cases.infraestructura.resolver_vinculacion_use_case import ResolverVinculacionUseCase
from src.telemetry.application.use_cases.infraestructura.corregir_vinculacion_use_case import CorregirVinculacionUseCase
from src.telemetry.application.use_cases.infraestructura.procesar_avisos_vinculacion_use_case import ProcesarAvisosVinculacionUseCase
from src.telemetry.infrastructure.dto.resolver_vinculacion_dto import ResolverVinculacionDTO
from src.telemetry.infrastructure.dto.corregir_vinculacion_dto import CorregirVinculacionDTO

_spec=importlib.util.spec_from_file_location('dev44_datos_m02',Path(__file__).with_name('test_inc_m09_64_g31_vinculacion_ingesta.py'))
h=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(h)
pytestmark=pytest.mark.integration


@pytest.fixture
def usuario(crear_usuario_db):return crear_usuario_db(id_rol=1)['id_usuario']


@pytest.fixture
def area(db_session,usuario):return h._area(db_session,usuario)


@pytest.fixture
def motor_exclusivo(integration_engine):
    url=integration_engine.url
    if url.host not in ('127.0.0.1','localhost','::1'):
        pytest.skip('La prueba con commits requiere PostgreSQL local aislado.')
    nombre='dev44_test_'+uuid.uuid4().hex
    admin=create_engine(url.set(database='postgres'),isolation_level='AUTOCOMMIT')
    motor=None
    creado=False
    try:
        with admin.connect() as c:c.execute(text(f'CREATE DATABASE "{nombre}"'))
        creado=True
        nueva=url.set(database=nombre).render_as_string(hide_password=False)
        entorno=os.environ|{'DATABASE_URL':nueva,'ALEMBIC_DATABASE_URL':nueva,'TEST_DATABASE_URL':nueva}
        r=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],env=entorno,capture_output=True,text=True,timeout=180)
        assert r.returncode==0,r.stdout[-2000:]+r.stderr[-2000:]
        motor=create_engine(nueva,use_insertmanyvalues=False)
        yield motor,entorno
    finally:
        if motor is not None:motor.dispose()
        if creado:
            with admin.connect() as c:c.execute(text(f'DROP DATABASE "{nombre}" WITH (FORCE)'))
        admin.dispose()


def activo(db,area,usuario,*,tipo='INDIVIDUAL',inicio=None):
    inicio=inicio or datetime.now(timezone.utc)-timedelta(days=2)
    identificador=h._activo(db,area,usuario,tipo=tipo)
    db.execute(text('UPDATE modulo2.activos_biologicos SET fecha_creacion=:fecha WHERE id_activo_biologico=:id'),{'fecha':inicio,'id':identificador})
    db.execute(text('''UPDATE modulo2.historial_infraestructura_activo SET fecha_inicio=:fecha
        WHERE id_activo_biologico=:id AND fecha_fin IS NULL'''),{'id':identificador,'fecha':inicio})
    snapshot={'id_especie':2,'detalle_individual':{'fecha_nacimiento':(inicio-timedelta(days=30)).isoformat()}}
    db.execute(text('''INSERT INTO modulo2.historial_activos
        (id_activo_biologico,version,tipo_evento,json_snapshot,fecha_evento,id_usuario)
        VALUES (:id,1,'CREACION',CAST(:json AS jsonb),:fecha,:u)'''),
        {'id':identificador,'json':json.dumps(snapshot),'fecha':inicio,'u':usuario})
    return identificador


def lectura(db,area,usuario,*,captura=None,configurada=True,dispositivo=None):
    captura=captura or datetime.now(timezone.utc)-timedelta(minutes=1)
    if dispositivo is None:
        dispositivo=db.execute(text('''INSERT INTO modulo9.dispositivos_iot(serial,descripcion,es_activo,fecha_creacion,id_infraestructura,id_tipo_dispositivo)
            VALUES (:s,'DEV-44',true,now(),:a,3) RETURNING id_dispositivo_iot'''),{'s':uuid.uuid4().hex[:20],'a':area}).scalar_one()
    sensor=db.execute(text("INSERT INTO modulo9.sensores(id_dispositivo_iot,es_activo,nombre) VALUES(:d,true,'RF61') RETURNING id_sensores"),{'d':dispositivo}).scalar_one()
    if configurada:
        db.execute(text('''INSERT INTO modulo9.sensores_areas_asociadas(id_sensor,id_dispositivo_iot,id_infraestructura,
            punto_instalacion,tiene_estado,fecha_asociacion,id_usuario)
            VALUES (:s,:d,:a,'DEV44',true,:fecha,:u)'''),
            {'s':sensor,'d':dispositivo,'a':area,'fecha':captura-timedelta(hours=1),'u':usuario})
    identificador=db.execute(text('''INSERT INTO modulo3.telemetrias(id_sensor,id_variable,id_dispositivo_iot,
        valor_crudo,valor_ajustado,timestamp_captura,timestamp_procesamiento,origen,estado_calidad,metadatos,categoria_variable,unidad_medida)
        VALUES (:s,1,:d,15,15,:fecha,now(),'TIEMPO_REAL','LECTURA_VALIDA','{}','HIDRICA','°C') RETURNING id_telemetria'''),
        {'s':sensor,'d':dispositivo,'fecha':captura}).scalar_one()
    db.commit()
    return identificador,captura


def vincular(db,identificador,area,captura):
    return VincularLecturaActivoUseCase(db,SqlAlchemyVinculacionLecturaRepository(db),ActivoBiologicoM02Adapter(db),
        SqlAlchemyBitacoraAuditoriaIotRepository(db)).execute(identificador,area,captura)


def test_catalogo_db13_columnas_y_vistas(db_session):
    estados=set(db_session.execute(text("SELECT unnest(enum_range(NULL::modulo3.enum_estado_vinculacion))::text")).scalars())
    assert estados=={'CONFIRMADA','AMBIGUA','SIN_VINCULAR','PENDIENTE_REVISION','SUPERADA'}
    columnas=set(db_session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_schema='modulo3' AND table_name='vinculaciones_lecturas'")).scalars())
    assert {'causa','contexto_activo'}<=columnas
    assert db_session.execute(text("SELECT to_regclass('modulo3.vw_m03_telemetria_contextualizada')")).scalar_one()
    assert db_session.execute(text("SELECT has_table_privilege(pg_get_userbyid(relowner),oid,'SELECT') FROM pg_class WHERE oid='modulo3.vw_m03_telemetria_contextualizada'::regclass")).scalar_one()


@pytest.mark.parametrize('tipo',['INDIVIDUAL','POBLACIONAL'])
def test_confirmada_snapshot_persistido_e_idempotencia(db_session,area,usuario,tipo):
    animal=activo(db_session,area,usuario,tipo=tipo)
    identificador,captura=lectura(db_session,area,usuario)
    v=vincular(db_session,identificador,area,captura)
    assert v.estado_vinculacion=='CONFIRMADA' and v.id_activo_biologico==animal
    assert v.contexto_activo['timestamp_captura']==captura.isoformat()
    assert vincular(db_session,identificador,area,captura).id_vinculacion_lectura==v.id_vinculacion_lectura
    assert db_session.execute(text('SELECT count(*) FROM modulo3.vinculaciones_lecturas WHERE id_telemetria=:id'),{'id':identificador}).scalar_one()==1


@pytest.mark.parametrize('configurada,causa',[(True,'SIN_ACTIVOS_EN_ESTRUCTURA'),(False,'CONFIGURACION_INCOMPLETA')])
def test_causas_reales_y_auditoria_sin_alterar_lectura(db_session,area,usuario,configurada,causa):
    identificador,captura=lectura(db_session,area,usuario,configurada=configurada)
    previo=dict(db_session.execute(text('SELECT * FROM modulo3.telemetrias WHERE id_telemetria=:id'),{'id':identificador}).mappings().one())
    v=vincular(db_session,identificador,area,captura)
    assert v.causa==causa and v.estado_vinculacion=='SIN_VINCULAR'
    evento=db_session.execute(text("SELECT accion_detallada FROM modulo3.bitacora_auditoria_iot WHERE tipo_evento='SIN_VINCULAR' AND entidad_afectada_id=:id"),{'id':str(v.id_vinculacion_lectura)}).scalar_one()
    assert evento['causa']==causa
    assert dict(db_session.execute(text('SELECT * FROM modulo3.telemetrias WHERE id_telemetria=:id'),{'id':identificador}).mappings().one())==previo


def test_ambiguedad_conserva_candidatos_y_fallo_aviso_no_borra_estado(db_session,area,usuario):
    candidatos=[activo(db_session,area,usuario),activo(db_session,area,usuario)]
    identificador,captura=lectura(db_session,area,usuario)
    v=vincular(db_session,identificador,area,captura)
    assert v.estado_vinculacion=='PENDIENTE_REVISION'
    assert v.contexto_activo['candidatos']==sorted(candidatos)
    with pytest.raises(ServiceUnavailableError):
        ProcesarAvisosVinculacionUseCase(SqlAlchemyVinculacionLecturaRepository(db_session)).execute(identificador)
    assert SqlAlchemyVinculacionLecturaRepository(db_session).vigente(identificador).estado_vinculacion=='PENDIENTE_REVISION'


def test_contexto_usa_medicion_anterior_y_snapshot_no_cambia(db_session,area,usuario):
    animal=activo(db_session,area,usuario)
    identificador,captura=lectura(db_session,area,usuario)
    def peso(fecha,valor):
        evento=db_session.execute(text('''INSERT INTO modulo2.eventos_activos(id_activo_biologico,fecha,descripcion,id_usuario)
            VALUES (:id,:fecha,'Medicion DEV44',:u) RETURNING id_eventos'''),{'id':animal,'fecha':fecha,'u':usuario}).scalar_one()
        db_session.execute(text("INSERT INTO modulo2.eventos_crecimeinto(id_evento,tipo_medicion,valor_medicion,unidad_medida) VALUES(:id,'PESO',:valor,'kg')"),{'id':evento,'valor':valor})
    peso(captura-timedelta(seconds=10),100)
    peso(captura+timedelta(seconds=10),999)
    v=vincular(db_session,identificador,area,captura)
    assert v.contexto_activo['peso_referencia']['valor_medicion']=='100.00'
    assert v.contexto_activo['peso_referencia']['unidad_medida']=='kg'
    original=json.loads(json.dumps(v.contexto_activo))
    peso(captura+timedelta(seconds=20),1500)
    db_session.commit();db_session.expire_all()
    assert SqlAlchemyVinculacionLecturaRepository(db_session).obtener_por_id(v.id_vinculacion_lectura).contexto_activo==original


def test_traslado_supera_origen_conserva_historia_y_destino_abre_su_lectura(db_session,area,usuario):
    destino=h._area(db_session,usuario);animal=activo(db_session,area,usuario)
    identificador,captura=lectura(db_session,area,usuario)
    v=vincular(db_session,identificador,area,captura)
    fecha=datetime.now(timezone.utc)-timedelta(seconds=20)
    db_session.execute(text('UPDATE modulo2.historial_infraestructura_activo SET fecha_fin=:f WHERE id_activo_biologico=:id AND fecha_fin IS NULL'),{'f':fecha,'id':animal})
    db_session.execute(text('''INSERT INTO modulo2.historial_infraestructura_activo(id_activo_biologico,id_infraestructura,fecha_inicio,id_usuario_registro)
        VALUES(:id,:area,:fecha,:u)'''),{'id':animal,'area':destino,'fecha':fecha,'u':usuario})
    adapter=VinculacionTrasladoM03Adapter(db_session)
    kwargs=dict(id_activo=animal,origen=area,destino=destino,fecha_efectiva=fecha,id_movimiento=uuid.uuid4().int%(10**8),id_usuario=usuario)
    adapter.procesar(**kwargs);adapter.procesar(**kwargs);db_session.commit()
    evento=db_session.execute(text("SELECT entidad_afectada_tipo,accion_detallada FROM modulo3.bitacora_auditoria_iot WHERE tipo_evento='TRASLADO_PROCESADO' AND accion_detallada->>'id_movimiento'=:id"),{'id':str(kwargs['id_movimiento'])}).one()
    assert evento[0] is None and evento[1]['id_movimiento']==kwargs['id_movimiento']
    repo=SqlAlchemyVinculacionLecturaRepository(db_session)
    vieja=repo.obtener_por_id(v.id_vinculacion_lectura)
    assert vieja.estado_vinculacion=='SUPERADA' and vieja.fecha_fin_vinculacion==fecha
    assert vieja.id_infraestructura==area and vieja.contexto_activo==v.contexto_activo
    assert repo.vigente(identificador) is None
    assert [a.id_activo_biologico for a in ActivoBiologicoM02Adapter(db_session).obtener_activos_en_momento(area,captura)]==[animal]
    assert not ActivoBiologicoM02Adapter(db_session).obtener_activos_en_momento(area,fecha)
    nuevo,cap=lectura(db_session,destino,usuario,captura=fecha+timedelta(seconds=1))
    assert vincular(db_session,nuevo,destino,cap).id_activo_biologico==animal


def test_periodo_cerrado_inmutable_y_rollback_traslado(db_session,area,usuario):
    animal=activo(db_session,area,usuario);identificador,captura=lectura(db_session,area,usuario)
    v=vincular(db_session,identificador,area,captura)
    with pytest.raises(RuntimeError):
        with db_session.begin_nested():
            VinculacionTrasladoM03Adapter(db_session).procesar(id_activo=animal,origen=area,destino=area+1,
                fecha_efectiva=datetime.now(timezone.utc),id_movimiento=123444,id_usuario=usuario)
            raise RuntimeError('fallo de prueba antes del commit RF48')
    assert SqlAlchemyVinculacionLecturaRepository(db_session).obtener_por_id(v.id_vinculacion_lectura).estado_vinculacion=='CONFIRMADA'


def test_manual_no_permite_activo_fuera_del_area_y_finca(db_session,area,usuario):
    otra=h._area(db_session,usuario);animal=activo(db_session,otra,usuario)
    identificador,captura=lectura(db_session,area,usuario);v=vincular(db_session,identificador,area,captura)
    uc=ResolverVinculacionUseCase(db_session,SqlAlchemyVinculacionLecturaRepository(db_session),activo_port=ActivoBiologicoM02Adapter(db_session))
    dto=ResolverVinculacionDTO(id_activo_biologico=animal,modelo_manejo='INDIVIDUAL')
    with pytest.raises(NotFoundError):uc.execute(v.id_vinculacion_lectura,dto,usuario,ids_fincas_permitidas=[])
    with pytest.raises(BusinessRuleError):uc.execute(v.id_vinculacion_lectura,dto,usuario)
    assert SqlAlchemyVinculacionLecturaRepository(db_session).vigente(identificador).id_activo_biologico is None


def test_correccion_nuevo_registro_supera_sin_sobrescribir_contexto(db_session,area,usuario):
    primero=activo(db_session,area,usuario);segundo=activo(db_session,area,usuario)
    identificador,captura=lectura(db_session,area,usuario);pendiente=vincular(db_session,identificador,area,captura)
    repo=SqlAlchemyVinculacionLecturaRepository(db_session);port=ActivoBiologicoM02Adapter(db_session)
    anterior=ResolverVinculacionUseCase(db_session,repo,activo_port=port).execute(pendiente.id_vinculacion_lectura,
        ResolverVinculacionDTO(id_activo_biologico=primero,modelo_manejo='INDIVIDUAL'),usuario)
    original=json.loads(json.dumps(anterior.contexto_activo))
    nueva=CorregirVinculacionUseCase(db_session,repo,activo_port=port).execute(anterior.id_vinculacion_lectura,
        CorregirVinculacionDTO(id_activo_biologico=segundo,modelo_manejo='INDIVIDUAL',motivo='Correccion documentada DEV44'),usuario)
    vieja=repo.obtener_por_id(anterior.id_vinculacion_lectura)
    assert vieja.estado_vinculacion=='SUPERADA' and vieja.contexto_activo==original
    assert nueva.id_activo_biologico==segundo and nueva.estado_vinculacion=='CONFIRMADA'
    assert nueva.id_vinculacion_reemplazada==vieja.id_vinculacion_lectura


def test_dos_vinculaciones_concurrentes_una_fila(motor_exclusivo):
    motor,_=motor_exclusivo
    with Session(motor) as db:
        usuario=db.execute(text('SELECT min(id_usuario) FROM modulo1.usuarios')).scalar_one()
        area=h._area(db,usuario);activo(db,area,usuario)
        identificador,captura=lectura(db,area,usuario)
    def ejecutar(_):
        with Session(motor) as db:return vincular(db,identificador,area,captura).id_vinculacion_lectura
    with ThreadPoolExecutor(max_workers=2) as executor:ids=list(executor.map(ejecutar,range(2)))
    assert ids[0]==ids[1]
    with motor.connect() as c:
        assert c.execute(text('SELECT count(*) FROM modulo3.vinculaciones_lecturas WHERE id_telemetria=:id'),{'id':identificador}).scalar_one()==1


def test_migracion_reversible_preserva_grants_y_vistas_con_filtro(motor_exclusivo):
    motor,entorno=motor_exclusivo
    with motor.begin() as c:
        c.execute(text("CREATE VIEW modulo3.dev44_vista_prueba WITH (security_barrier=true) AS SELECT id_vinculacion_lectura,estado_vinculacion FROM modulo3.vinculaciones_lecturas WHERE estado_vinculacion='CONFIRMADA'::modulo3.enum_estado_vinculacion"))
        c.execute(text('ALTER VIEW modulo3.dev44_vista_prueba OWNER TO sgpmp_owner'))
        c.execute(text('GRANT SELECT ON modulo3.vinculaciones_lecturas TO sgpmp_owner'))
        c.execute(text('GRANT SELECT ON modulo3.dev44_vista_prueba TO sgpmp_app WITH GRANT OPTION'))
        c.execute(text("COMMENT ON VIEW modulo3.dev44_vista_prueba IS 'DEV44 conserva comentario'"))
        c.execute(text("COMMENT ON COLUMN modulo3.dev44_vista_prueba.estado_vinculacion IS 'Estado de vinculacion'"))
    def comprobar(estado):
        with motor.connect() as c:
            fila=c.execute(text("SELECT pg_get_userbyid(relowner),reloptions,obj_description(oid,'pg_class') FROM pg_class WHERE oid='modulo3.dev44_vista_prueba'::regclass")).one()
            assert fila[0]=='sgpmp_owner' and fila[1]==['security_barrier=true'] and fila[2]=='DEV44 conserva comentario'
            assert c.execute(text("SELECT has_table_privilege('sgpmp_app','modulo3.dev44_vista_prueba','SELECT WITH GRANT OPTION')")).scalar_one()
            assert estado in c.execute(text("SELECT pg_get_viewdef('modulo3.dev44_vista_prueba'::regclass,true)")).scalar_one()
            c.execute(text('SELECT * FROM modulo3.dev44_vista_prueba LIMIT 0'))
    comprobar('CONFIRMADA')
    for direccion,revision,estado in [('downgrade','e5a3c9b17d42','VINCULADA'),('upgrade','head','CONFIRMADA')]:
        r=subprocess.run([sys.executable,'-m','alembic',direccion,revision],env=entorno,capture_output=True,text=True,timeout=90)
        assert r.returncode==0,r.stdout[-2000:]+r.stderr[-2000:]
        comprobar(estado)


def ejecutar_etapa(db,worker,etapa,identificador):
    with unidad_postcommit(db.get_bind(),identidad=False) as unidad:
        if not unidad.reclamar(etapa,identificador):return False
        worker.acciones[etapa](unidad.db,identificador)
        unidad.registrar(etapa,identificador)
        unidad.confirmar()
        return True


def test_etapa_postcommit_aviso_pendiente_no_borra_vinculo_y_recupera(db_session,area,usuario):
    activo(db_session,area,usuario);activo(db_session,area,usuario)
    identificador,captura=lectura(db_session,area,usuario)
    worker=construir_procesador(db_session.get_bind(),identidad=False)
    assert ejecutar_etapa(db_session,worker,EtapaPostcommit.RF61,identificador)
    with pytest.raises(ServiceUnavailableError):ejecutar_etapa(db_session,worker,EtapaPostcommit.RF61_AVISOS,identificador)
    repo=SqlAlchemyVinculacionLecturaRepository(db_session)
    assert repo.vigente(identificador).estado_vinculacion=='PENDIENTE_REVISION'
    avisos=Mock();avisos.ambiguedad.return_value=True
    recuperado=construir_procesador(db_session.get_bind(),identidad=False,avisos_vinculacion=avisos)
    assert ejecutar_etapa(db_session,recuperado,EtapaPostcommit.RF61_AVISOS,identificador)
    assert not ejecutar_etapa(db_session,recuperado,EtapaPostcommit.RF61_AVISOS,identificador)
    avisos.ambiguedad.assert_called_once()
    assert len(avisos.ambiguedad.call_args.args[0].contexto_activo['candidatos'])==2
    # Solo el puerto de entrega es un doble: no acredita email/push ni evento M01.


def test_historial_no_verificable_es_revision_y_no_estructura_vacia(db_session,area,usuario):
    animal=h._activo(db_session,area,usuario,con_historial=False)
    db_session.execute(text('UPDATE modulo2.activos_biologicos SET fecha_creacion=now()-interval \'1 day\' WHERE id_activo_biologico=:id'),{'id':animal})
    identificador,captura=lectura(db_session,area,usuario)
    v=vincular(db_session,identificador,area,captura)
    assert v.estado_vinculacion=='PENDIENTE_REVISION' and v.causa is None
    assert v.contexto_activo['historial_consistente'] is False


def test_activo_baja_posterior_no_excluye_captura_historica(db_session,area,usuario):
    animal=activo(db_session,area,usuario)
    identificador,captura=lectura(db_session,area,usuario)
    db_session.execute(text('''INSERT INTO modulo2.historicos_estados_activos(id_activo_biologico,id_estado_nuevo,
        id_estado_anterior,fecha_cambio,motivo_cambio,modulo_origen,id_usuario)
        VALUES (:id,6,1,:fecha,'Baja de prueba','MANUAL',:u)'''),{'id':animal,'fecha':captura+timedelta(seconds=10),'u':usuario})
    assert vincular(db_session,identificador,area,captura).id_activo_biologico==animal


def test_fase_historica_preserva_identificador_y_nombre(db_session,area,usuario):
    animal=activo(db_session,area,usuario)
    identificador,captura=lectura(db_session,area,usuario)
    biologico=db_session.execute(text("""INSERT INTO modulo9.ciclos_biologicos(nombre,duracion_dias,id_especie)
        VALUES (:n,30,2) RETURNING id_ciclo_biologico"""),{'n':'DEV44 '+uuid.uuid4().hex[:12]}).scalar_one()
    ciclo=db_session.execute(text("""INSERT INTO modulo9.ciclos_productivos(nombre,duracion_dias,id_ciclo_biologico)
        VALUES (:n,30,:b) RETURNING id_ciclo_productivo"""),{'n':'Fase DEV44 '+uuid.uuid4().hex[:8],'b':biologico}).scalar_one()
    fase=db_session.execute(text('''INSERT INTO modulo9.ciclos_productivos_biologicos(id_ciclo_productivo,id_ciclo_biologico)
        VALUES (:c,:b) RETURNING id_ciclos_productivo_biologico'''),{'c':ciclo,'b':biologico}).scalar_one()
    db_session.execute(text('''INSERT INTO modulo2.gestiones_fases(id_activo_biologico,id_ciclo_productiva,
        id_ciclos_productivo_biologico,fecha_inicio,es_activa,id_usuario) VALUES (:id,:c,:fase,:fecha,true,:u)'''),
        {'id':animal,'c':ciclo,'fase':fase,'fecha':captura-timedelta(hours=1),'u':usuario})
    v=vincular(db_session,identificador,area,captura)
    assert v.contexto_activo['fase_productiva']['id_ciclo_productiva']==ciclo
    assert v.contexto_activo['fase_productiva']['id_ciclos_productivo_biologico']==fase
    assert v.contexto_activo['fase_productiva']['id_ciclo_biologico']==biologico
    assert v.contexto_activo['fase_productiva']['nombre']
    assert v.contexto_activo['fecha_nacimiento']
    assert v.contexto_activo['edad_dias'] is None
    assert 'edad_dias' in v.contexto_activo['datos_no_disponibles']


@pytest.mark.parametrize('fallar',[False,True])
def test_rf48_uc_integra_cierre_o_revierte_todo(db_session,area,usuario,fallar):
    from src.biological_assets.application.use_cases.gestion.registrar_transferencia_use_case import RegistrarTransferenciaUseCase
    from src.biological_assets.infrastructure.repositories.activo_biologico_repository import SqlAlchemyActivoBiologicoRepository
    from src.biological_assets.infrastructure.repositories.transferencia_repository import SqlAlchemyTransferenciaRepository
    from src.biological_assets.infrastructure.dto.registrar_transferencia_dto import RegistrarTransferenciaDTO
    from src.shared.fechas import hoy_colombia
    destino=db_session.execute(text('''INSERT INTO modulo9.infraestructuras(nombre,id_finca,superficie,es_activo,tipo)
        SELECT 'Destino DEV44',id_finca,100,true,'Estanque' FROM modulo9.infraestructuras
        WHERE id_infraestructura=:id RETURNING id_infraestructura'''),{'id':area}).scalar_one()
    animal=activo(db_session,area,usuario);identificador,captura=lectura(db_session,area,usuario)
    v=vincular(db_session,identificador,area,captura)
    finca=db_session.execute(text('SELECT id_finca FROM modulo9.infraestructuras WHERE id_infraestructura=:id'),{'id':area}).scalar_one()
    infras=Mock()
    infras.obtener_activa.side_effect=lambda i:SimpleNamespace(id_infraestructura=i,nombre='Origen' if i==area else 'Destino',
        id_especie=2,id_finca=finca,tipo='Estanque',superficie=100,capacidad_maxima=10000)
    infras.es_tipo_compatible.return_value=True
    infras.calcular_ocupacion.return_value=0
    puente=VinculacionTrasladoM03Adapter(db_session)
    if fallar:
        real=puente.procesar
        def romper(**kwargs):
            real(**kwargs)
            raise RuntimeError('fallo de prueba entre RF61 y commit RF48')
        puente.procesar=romper
    uc=RegistrarTransferenciaUseCase(db_session,SqlAlchemyActivoBiologicoRepository(db_session),
        SqlAlchemyTransferenciaRepository(db_session),infras,Mock(),vinculacion_traslado_port=puente)
    dto=RegistrarTransferenciaDTO(infraestructura_origen_id=area,infraestructura_destino_id=destino,
        fecha_transferencia=hoy_colombia(),motivo_transferencia='Traslado de integracion DEV44')
    if fallar:
        with pytest.raises(RuntimeError):uc.execute(animal,dto,SimpleNamespace(id_usuario=usuario))
    else:uc.execute(animal,dto,SimpleNamespace(id_usuario=usuario))
    actual=db_session.execute(text('SELECT id_infraestructura FROM modulo2.activos_biologicos WHERE id_activo_biologico=:id'),{'id':animal}).scalar_one()
    estado=SqlAlchemyVinculacionLecturaRepository(db_session).obtener_por_id(v.id_vinculacion_lectura).estado_vinculacion
    assert (actual,estado)==((area,'CONFIRMADA') if fallar else (destino,'SUPERADA'))
    assert db_session.execute(text('SELECT count(*) FROM modulo2.movimientos WHERE id_activo_biologico=:id'),{'id':animal}).scalar_one()==(0 if fallar else 1)


def test_buffer_tardio_conserva_periodo_cerrado_sin_duplicar(db_session,area,usuario):
    animal=activo(db_session,area,usuario)
    identificador,captura=lectura(db_session,area,usuario)
    fin=captura+timedelta(seconds=10)
    db_session.execute(text('UPDATE modulo2.historial_infraestructura_activo SET fecha_fin=:fin WHERE id_activo_biologico=:id AND fecha_fin IS NULL'),{'id':animal,'fin':fin})
    v=vincular(db_session,identificador,area,captura)
    repo=SqlAlchemyVinculacionLecturaRepository(db_session)
    assert v.estado_vinculacion=='SUPERADA' and v.fecha_fin_vinculacion==fin
    assert repo.vigente(identificador) is None
    assert vincular(db_session,identificador,area,captura).id_vinculacion_lectura==v.id_vinculacion_lectura
    from src.telemetry.infrastructure.repositories.lectura_postcommit_repository import SqlAlchemyLecturaPostcommitRepository
    assert SqlAlchemyLecturaPostcommitRepository(db_session).vinculacion_historica(identificador)['id_activo_biologico']==animal


def test_traslado_no_espera_lock_dispositivo_y_reintento_cierra_una_vez(motor_exclusivo):
    from src.shared.errors import ConflictError
    motor,_=motor_exclusivo
    with Session(motor) as db:
        usuario=db.execute(text('SELECT min(id_usuario) FROM modulo1.usuarios')).scalar_one()
        area=h._area(db,usuario);animal=activo(db,area,usuario)
        identificador,captura=lectura(db,area,usuario)
        v=vincular(db,identificador,area,captura)
        dispositivo=db.execute(text('SELECT id_dispositivo_iot FROM modulo3.telemetrias WHERE id_telemetria=:id'),{'id':identificador}).scalar_one()
    argumentos=dict(id_activo=animal,origen=area,destino=area,fecha_efectiva=datetime.now(timezone.utc),id_movimiento=444123,id_usuario=usuario)
    with Session(motor) as worker,Session(motor) as traslado:
        worker.execute(text('SELECT pg_advisory_xact_lock(3505,:id)'),{'id':dispositivo})
        traslado.execute(text("SET LOCAL statement_timeout='3s'"))
        traslado.execute(text('SELECT id_activo_biologico FROM modulo2.activos_biologicos WHERE id_activo_biologico=:id FOR UPDATE'),{'id':animal})
        with pytest.raises(ConflictError):VinculacionTrasladoM03Adapter(traslado).procesar(**argumentos)
        traslado.rollback();worker.rollback()
        assert SqlAlchemyVinculacionLecturaRepository(traslado).obtener_por_id(v.id_vinculacion_lectura).estado_vinculacion=='CONFIRMADA'
        VinculacionTrasladoM03Adapter(traslado).procesar(**argumentos)
        VinculacionTrasladoM03Adapter(traslado).procesar(**argumentos)
        traslado.commit()
        assert SqlAlchemyVinculacionLecturaRepository(traslado).obtener_por_id(v.id_vinculacion_lectura).estado_vinculacion=='SUPERADA'
        assert traslado.execute(text("SELECT count(*) FROM modulo3.bitacora_auditoria_iot WHERE tipo_evento='TRASLADO_PROCESADO' AND accion_detallada->>'id_movimiento'='444123'")).scalar_one()==1


def test_destinatarios_requieren_permisos_cuenta_y_finca(db_session,area,usuario,crear_usuario_db):
    # El fixture crea cuentas; los permisos se preparan explicitamente en esta transaccion aislada.
    rol=db_session.execute(text("SELECT id_rol FROM modulo1.roles WHERE NOT es_protegido ORDER BY id_rol LIMIT 1")).scalar_one()
    permitido=crear_usuario_db(id_rol=rol)['id_usuario']
    ajeno=crear_usuario_db(id_rol=rol)['id_usuario']
    for recurso,accion in [('vinculaciones_lecturas',3),('activos_biologicos',2)]:
        db_session.execute(text("""INSERT INTO modulo1.permisos(nombre,id_recurso,id_accion,id_rol,es_activo)
            SELECT 'DEV44 permiso de prueba',id_recurso,:accion,:rol,true FROM modulo1.recursos WHERE nombre_recurso=:recurso
            ON CONFLICT (id_recurso,id_accion,id_rol) DO UPDATE SET es_activo=true"""),{'accion':accion,'rol':rol,'recurso':recurso})
    finca=db_session.execute(text('SELECT id_finca FROM modulo9.infraestructuras WHERE id_infraestructura=:id'),{'id':area}).scalar_one()
    db_session.execute(text('INSERT INTO modulo9.usuarios_fincas(id_usuario,id_finca) VALUES (:u,:f)'),{'u':permitido,'f':finca})
    adapter=DestinatariosVinculacionM01Adapter(db_session)
    assert permitido in adapter.obtener(area) and ajeno not in adapter.obtener(area)
    db_session.execute(text('UPDATE modulo9.usuarios_fincas SET es_activo=false WHERE id_usuario=:u'),{'u':permitido})
    assert permitido not in adapter.obtener(area)
    assert permitido not in adapter.obtener(area,administradores=True)



def test_resolucion_http_jwt_permiso_y_alcance(db_session,area,usuario,crear_usuario_db,crear_auth_headers,client,integration_app):
    from src.telemetry.infrastructure.routers.vinculacion_router import router
    if not any(getattr(r,'path',None)=='/iot/vinculaciones' for r in integration_app.routes):
        integration_app.include_router(router)
    rol=db_session.execute(text('SELECT id_rol FROM modulo1.roles WHERE NOT es_protegido ORDER BY id_rol LIMIT 1')).scalar_one()
    cuenta=crear_usuario_db(id_rol=rol)
    animal=activo(db_session,area,usuario)
    identificador,captura=lectura(db_session,area,usuario,configurada=False)
    v=vincular(db_session,identificador,area,captura)
    recurso=db_session.execute(text("SELECT id_recurso FROM modulo1.recursos WHERE nombre_recurso='vinculaciones_lecturas'")).scalar_one()
    db_session.execute(text('UPDATE modulo1.permisos SET es_activo=false WHERE id_rol=:rol AND id_recurso=:r AND id_accion=3'),{'rol':rol,'r':recurso})
    headers=crear_auth_headers(cuenta)
    ruta=f'/iot/vinculaciones/{v.id_vinculacion_lectura}/resolver'
    payload={'id_activo_biologico':animal,'modelo_manejo':'INDIVIDUAL'}
    assert client.patch(ruta,json=payload).status_code==401
    assert client.patch(ruta,json=payload,headers=headers).status_code==403
    db_session.execute(text("""INSERT INTO modulo1.permisos(nombre,id_recurso,id_accion,id_rol,es_activo)
        VALUES ('DEV44 HTTP permiso de prueba',:r,3,:rol,true)
        ON CONFLICT (id_recurso,id_accion,id_rol) DO UPDATE SET es_activo=true"""),{'r':recurso,'rol':rol})
    assert client.patch(ruta,json=payload,headers=headers).status_code==404
    finca=db_session.execute(text('SELECT id_finca FROM modulo9.infraestructuras WHERE id_infraestructura=:id'),{'id':area}).scalar_one()
    db_session.execute(text('INSERT INTO modulo9.usuarios_fincas(id_usuario,id_finca) VALUES (:u,:f)'),{'u':cuenta['id_usuario'],'f':finca})
    respuesta=client.patch(ruta,json=payload,headers=headers)
    assert respuesta.status_code==200,respuesta.text
    assert respuesta.json()['estado_vinculacion']=='CONFIRMADA'
    assert respuesta.json()['contexto_activo']['id_activo_biologico']==animal

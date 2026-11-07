# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-133-G170 RF-62: validar lote real, historial, parametros, rollback y auditoria con rol API. |
"""PostgreSQL real y rol sgpmp_app; la telemetría fuente permanece inmutable."""
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import json
from uuid import uuid4
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session
from tests.integration.test_inc_m03_104_g165_motor_calidad import (
    rutas_g165,equipo_g165,insertar_serie,instantanea)
from src.telemetry.application.use_cases.calidad.evaluar_calidad_telemetria_use_case import EvaluarCalidadTelemetriaUseCase
from src.telemetry.infrastructure.repositories.telemetria_calidad_repository import SqlAlchemyTelemetriaCalidadRepository
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import SqlAlchemyBitacoraAuditoriaIotRepository
from src.shared.errors import ServiceUnavailableError

pytestmark=pytest.mark.integration


@pytest.fixture
def lote_g170(client,db_session,equipo_g165):
    e=equipo_g165
    primer=insertar_serie(db_session,e,[19.8,20.2]*10,20,offset=3.5294)
    fuente=db_session.execute(text('SELECT timestamp_captura FROM modulo3.telemetrias WHERE id_telemetria=:id'),{'id':primer}).scalar_one()
    ids=[primer]
    for i in range(1,6):
        identificador=db_session.execute(text('''INSERT INTO modulo3.telemetrias
            (id_sensor,id_variable,id_dispositivo_iot,valor_crudo,valor_ajustado,timestamp_captura,
             timestamp_procesamiento,origen,estado_calidad,calibrado,categoria_variable,unidad_medida,
             valor_agregado,tipo_dato,metadatos,frecuencia_muestreo_min,parametros_calibracion)
            VALUES (:s,9,:d,:v,:v+3.5294,:ts,now(),'TIEMPO_REAL','LECTURA_VALIDA',true,
                'AMBIENTAL','°C',false,'CRUDO','{}',10,jsonb_build_object('offset',3.5294,'ganancia',1)) RETURNING id_telemetria'''),
            {'s':e['sensor'],'d':e['dispositivo'],'v':20+0.2*(i%2),'ts':fuente+timedelta(seconds=i)}).scalar_one()
        ids.append(identificador)
    db_session.commit()
    for identificador in ids:
        r=client.post(f'/iot/calidad/{identificador}/evaluar',headers=e['headers'])
        assert r.status_code==201,r.text
        assert r.json()['flags_detectados']['posible_drift']['activo'] is True
    rango=db_session.execute(text('SELECT min(timestamp_evaluacion),max(timestamp_evaluacion) FROM modulo3.telemetria_calidad WHERE id_sensor=:s'),{'s':e['sensor']}).one()
    solicitud={'id_sensor':e['sensor'],'fecha_desde':(rango[0]-timedelta(seconds=1)).isoformat(),
        'fecha_hasta':(rango[1]+timedelta(seconds=1)).isoformat(),
        'causa_documentada':'Offset de calibracion incorrecto genero drift falso en las evaluaciones',
        'parametros_correctos':{'offset':0,'ganancia':1}}
    return {**e,'ids':ids,'solicitud':solicitud}


def evaluaciones(db,sensor):
    return db.execute(text('SELECT to_jsonb(c) FROM modulo3.telemetria_calidad c WHERE id_sensor=:s ORDER BY id_telemetria,timestamp_evaluacion,id_evaluacion'),{'s':sensor}).scalars().all()


def test_lote_seis_crea_sustitutas_con_parametros_auditoria_e_inmutabilidad(client,db_session,lote_g170):
    e=lote_g170
    original=instantanea(db_session,e['sensor'])
    anteriores=evaluaciones(db_session,e['sensor'])
    r=client.post('/iot/calidad/reevaluar',json=e['solicitud'],headers=e['headers'])
    assert r.status_code==200,r.text
    assert r.json()=={'evaluaciones_superadas':6,'evaluaciones_creadas':6}
    todas=evaluaciones(db_session,e['sensor'])
    assert len(todas)==12
    for previa in anteriores:
        historia=[ev for ev in todas if ev['id_telemetria']==previa['id_telemetria']]
        assert len(historia)==2
        vieja=next(x for x in historia if x['estado_evaluacion']=='SUPERADA')
        nueva=next(x for x in historia if x['estado_evaluacion']=='VIGENTE')
        assert vieja['id_evaluacion']==previa['id_evaluacion']
        for key in ('indice_calidad','parametros_aplicados','parametros_calibracion_aplicados','flags_detectados','version_evaluacion'):
            assert vieja[key]==previa[key]
        assert nueva['id_evaluacion_superada']==vieja['id_evaluacion']
        assert nueva['motivo_reevaluacion']==e['solicitud']['causa_documentada']
        assert nueva['parametros_calibracion_aplicados']=={'offset':0,'ganancia':1}
        assert nueva['version_evaluacion'].startswith('rf62:')
        assert nueva['indice_calidad']==100
        assert nueva['apto_para_ia'] is True and nueva['apto_para_nic41'] is True
        assert not nueva['flags_detectados'].get('posible_drift',{}).get('activo',False)
        detalle=client.get(f"/iot/calidad/{nueva['id_telemetria']}",headers=e['headers'])
        assert detalle.status_code==200 and detalle.json()['id_evaluacion']==nueva['id_evaluacion']
    assert instantanea(db_session,e['sensor'])==original
    auditoria=db_session.execute(text("SELECT to_jsonb(a) FROM modulo3.bitacora_auditoria_iot a WHERE tipo_evento='REEVALUACION_CALIDAD_SOLICITADA' AND accion_detallada->>'id_sensor'=:s"),{'s':str(e['sensor'])}).scalar_one()
    d=auditoria['accion_detallada']
    assert d['evaluaciones_generadas']==d['evaluaciones_superadas']==6
    assert set(d['rango_lecturas_afectadas'])==set(e['ids'])
    assert len(d['sustituciones'])==len(d['parametros_anteriores'])==len(d['parametros_nuevos'])==6
    assert auditoria['id_usuario'] is not None
    assert all(p['calibracion']=={'offset':0,'ganancia':1} for p in d['parametros_nuevos'])
    assert {n['modulo'] for n in d['notificaciones_pendientes']}=={'M04','M06'}
    assert auditoria['resultado']=='PARCIAL' and len(auditoria['hash_integridad'])==64


@pytest.mark.parametrize('fase',['segunda_evaluacion','constraint','auditoria_lote','commit'])
def test_fallo_revierte_todas_las_sustitutas_y_conserva_vigentes(client,db_session,lote_g170,monkeypatch,fase):
    e=lote_g170
    antes=evaluaciones(db_session,e['sensor'])
    fuente=instantanea(db_session,e['sensor'])
    with monkeypatch.context() as fallos:
        if fase=='segunda_evaluacion':
            original=SqlAlchemyTelemetriaCalidadRepository.guardar
            contador=[]
            def fallar(self,ev):
                guardada=original(self,ev)
                contador.append(True)
                if len(contador)==2:raise ServiceUnavailableError('FALLO_PRUEBA','Fallo de persistencia inducido.')
                return guardada
            fallos.setattr(SqlAlchemyTelemetriaCalidadRepository,'guardar',fallar)
        elif fase=='constraint':
            original=SqlAlchemyTelemetriaCalidadRepository.guardar
            contador=[]
            def fallar(self,ev):
                contador.append(True)
                if len(contador)==2:ev.id_evaluacion_superada=uuid4()
                return original(self,ev)
            fallos.setattr(SqlAlchemyTelemetriaCalidadRepository,'guardar',fallar)
        elif fase=='auditoria_lote':
            original=SqlAlchemyBitacoraAuditoriaIotRepository.registrar
            def fallar(self,ev):
                guardado=original(self,ev)
                if ev.tipo_evento=='REEVALUACION_CALIDAD_SOLICITADA':
                    ev.id_evento=None
                    return ev
                return guardado
            fallos.setattr(SqlAlchemyBitacoraAuditoriaIotRepository,'registrar',fallar)
        else:
            original=db_session.commit
            def fallar():
                # Login y resolución del usuario confirman su propia transacción.
                nuevas=db_session.execute(text("SELECT count(*) FROM modulo3.telemetria_calidad WHERE id_sensor=:s AND id_evaluacion_superada IS NOT NULL"),{'s':e['sensor']}).scalar_one()
                if nuevas:raise ServiceUnavailableError('FALLO_PRUEBA','Fallo de commit inducido.')
                return original()
            fallos.setattr(db_session,'commit',fallar)
        r=client.post('/iot/calidad/reevaluar',json=e['solicitud'],headers=e['headers'])
    assert r.status_code==(400 if fase=='constraint' else 503),r.text
    assert 'INSERT INTO' not in r.text and 'psycopg' not in r.text
    assert evaluaciones(db_session,e['sensor'])==antes
    assert instantanea(db_session,e['sensor'])==fuente
    assert db_session.execute(text("SELECT count(*) FROM modulo3.bitacora_auditoria_iot WHERE tipo_evento='REEVALUACION_CALIDAD_SOLICITADA' AND accion_detallada->>'id_sensor'=:s"),{'s':str(e['sensor'])}).scalar_one()==0
    reintento=client.post('/iot/calidad/reevaluar',json=e['solicitud'],headers=e['headers'])
    assert reintento.status_code==200,reintento.text
    assert reintento.json()=={'evaluaciones_superadas':6,'evaluaciones_creadas':6}
    assert instantanea(db_session,e['sensor'])==fuente


@pytest.mark.parametrize('correcciones',[{'offset':'0'},{'k':0},{'N':3,'M':4},{'desconocido':1}])
def test_parametros_invalidos_no_superan_evaluaciones(client,db_session,lote_g170,correcciones):
    e=lote_g170
    antes=evaluaciones(db_session,e['sensor'])
    r=client.post('/iot/calidad/reevaluar',json={**e['solicitud'],'parametros_correctos':correcciones},headers=e['headers'])
    assert r.status_code==422,r.text
    assert r.json()['error_code']=='PARAMETROS_REEVALUACION_INVALIDOS'
    assert evaluaciones(db_session,e['sensor'])==antes


def test_parametros_estadisticos_corregidos_se_aplican_sin_escribir_m09(client,db_session,lote_g170):
    e=lote_g170
    antes=db_session.execute(text('SELECT jsonb_agg(to_jsonb(p) ORDER BY nombre_parametro) FROM modulo4.parametros_mlops p')).scalar_one()
    r=client.post('/iot/calidad/reevaluar',json={**e['solicitud'],'parametros_correctos':{'k':4,'M':4,'N':20,'P':4,'umbral_drift':20}},headers=e['headers'])
    assert r.status_code==200,r.text
    nuevas=[x for x in evaluaciones(db_session,e['sensor']) if x['estado_evaluacion']=='VIGENTE']
    assert len(nuevas)==6
    assert all(x['parametros_aplicados']['k']==4 and x['parametros_aplicados']['P']==4 for x in nuevas)
    assert all(not x['flags_detectados'].get('posible_drift',{}).get('activo') for x in nuevas)
    assert db_session.execute(text('SELECT jsonb_agg(to_jsonb(p) ORDER BY nombre_parametro) FROM modulo4.parametros_mlops p')).scalar_one()==antes


@pytest.mark.parametrize('rol',[2,4])
def test_reevaluacion_masiva_restringida_a_administrador(client,db_session,lote_g170,crear_usuario_db,crear_auth_headers,rol):
    e=lote_g170
    usuario=crear_usuario_db(id_rol=rol)
    headers=crear_auth_headers(usuario)
    antes=evaluaciones(db_session,e['sensor'])
    r=client.post('/iot/calidad/reevaluar',json=e['solicitud'],headers=headers)
    assert r.status_code==403,r.text
    assert evaluaciones(db_session,e['sensor'])==antes


def test_token_ausente_no_modifica_el_lote(client,db_session,lote_g170):
    e=lote_g170
    antes=evaluaciones(db_session,e['sensor'])
    r=client.post('/iot/calidad/reevaluar',json=e['solicitud'])
    assert r.status_code==401,r.text
    assert evaluaciones(db_session,e['sensor'])==antes


@pytest.mark.parametrize('causa',[None,'','Error'])
def test_causa_incompleta_con_evaluaciones_presentes_no_las_supera(client,db_session,lote_g170,causa):
    e=lote_g170
    antes=evaluaciones(db_session,e['sensor'])
    entrada={**e['solicitud'],'causa_documentada':causa}
    if causa is None:entrada.pop('causa_documentada')
    r=client.post('/iot/calidad/reevaluar',json=entrada,headers=e['headers'])
    assert r.status_code==400,r.text
    assert evaluaciones(db_session,e['sensor'])==antes


def test_rango_invertido_sin_sustituciones(client,db_session,lote_g170):
    e=lote_g170
    antes=evaluaciones(db_session,e['sensor'])
    r=client.post('/iot/calidad/reevaluar',json={**e['solicitud'],
        'fecha_desde':e['solicitud']['fecha_hasta'],'fecha_hasta':e['solicitud']['fecha_desde']},headers=e['headers'])
    assert r.status_code==422,r.text
    assert evaluaciones(db_session,e['sensor'])==antes


def test_extremos_iguales_con_una_evaluacion_exacta_conservan_consulta_inclusiva(client,db_session,lote_g170):
    e=lote_g170
    antes=evaluaciones(db_session,e['sensor'])
    objetivo=antes[0]
    r=client.post('/iot/calidad/reevaluar',json={**e['solicitud'],
        'fecha_desde':objetivo['timestamp_evaluacion'],'fecha_hasta':objetivo['timestamp_evaluacion']},headers=e['headers'])
    assert r.status_code==200,r.text
    assert r.json()=={'evaluaciones_superadas':1,'evaluaciones_creadas':1}


def test_inactividad_no_deja_lote_sin_vigentes(client,db_session,lote_g170):
    from tests.integration.test_dev43_calidad_temporal import periodo
    e=lote_g170
    antes=evaluaciones(db_session,e['sensor'])
    inicio=db_session.execute(text('SELECT min(timestamp_captura) FROM modulo3.telemetrias WHERE id_sensor=:s'),{'s':e['sensor']}).scalar_one()
    periodo(db_session,{'device':e['dispositivo'],'sensor':e['sensor']},inicio-timedelta(minutes=1))
    r=client.post('/iot/calidad/reevaluar',json=e['solicitud'],headers=e['headers'])
    assert r.status_code==422,r.text
    assert r.json()['error_code']=='REEVALUACION_OMITIDA_POR_INACTIVIDAD'
    assert evaluaciones(db_session,e['sensor'])==antes


def test_sucesivas_solicitudes_conservan_cadena_y_una_vigente(client,db_session,lote_g170):
    from datetime import datetime,timezone
    e=lote_g170
    solicitud={**e['solicitud'],'fecha_hasta':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}
    for paso in range(2):
        r=client.post('/iot/calidad/reevaluar',json={**solicitud,'causa_documentada':solicitud['causa_documentada']+f' correccion {paso}'},headers=e['headers'])
        assert r.status_code==200 and r.json()=={'evaluaciones_superadas':6,'evaluaciones_creadas':6},r.text
    todas=evaluaciones(db_session,e['sensor'])
    assert len(todas)==18
    for identificador in e['ids']:
        filas=[ev for ev in todas if ev['id_telemetria']==identificador]
        assert sum(ev['estado_evaluacion']=='VIGENTE' for ev in filas)==1
        assert sum(ev['id_evaluacion_superada'] is not None for ev in filas)==2
        causas={ev['motivo_reevaluacion'] for ev in filas if ev['id_evaluacion_superada'] is not None}
        assert causas=={solicitud['causa_documentada']+f' correccion {i}' for i in range(2)}


# La base separada permite commits reales visibles entre conexiones.
from tests.integration.test_dev43_calidad_temporal import concurrency_engine


def test_lotes_concurrentes_releen_la_vigente_y_no_rompen_la_cadena(concurrency_engine):
    from datetime import datetime,timezone
    from threading import Barrier
    from src.shared.database import como_sistema
    from src.telemetry.infrastructure.adapters.contexto_calidad_m09_rf60_adapter import ContextoCalidadM09RF60Adapter
    from src.telemetry.application.use_cases.calidad.solicitar_reevaluacion_use_case import SolicitarReevaluacionUseCase
    from src.telemetry.infrastructure.dto.solicitar_reevaluacion_dto import SolicitarReevaluacionDTO
    from tests.integration.test_dev43_calidad_temporal import h,serie,caso,evaluar
    with concurrency_engine.begin() as c:
        c.exec_driver_sql('GRANT USAGE ON SCHEMA modulo1,modulo3,modulo9 TO sgpmp_app')
        c.exec_driver_sql('GRANT SELECT ON modulo3.telemetrias,modulo3.periodos_inactividad,modulo9.variables_ambientales TO sgpmp_app')
        c.exec_driver_sql('GRANT SELECT,INSERT,UPDATE ON modulo3.telemetria_calidad TO sgpmp_app')
        c.exec_driver_sql('GRANT SELECT,INSERT ON modulo3.bitacora_auditoria_iot TO sgpmp_app')
    with Session(concurrency_engine) as db:
        equipo=h.hardware(db)
        ids1,ts1=serie(db,equipo)
        ids2,ts2=serie(db,equipo)
        db.commit()
        db.execute(text('SET LOCAL ROLE sgpmp_app'))
        with como_sistema(db):
            evaluar(caso(db,alertas=None),equipo,ids1,ts1)
        db.execute(text('SET LOCAL ROLE sgpmp_app'))
        with como_sistema(db):
            evaluar(caso(db,alertas=None),equipo,ids2,ts2)
    solicitud=SolicitarReevaluacionDTO(id_sensor=equipo['sensor'],
        fecha_desde=datetime.now(timezone.utc)-timedelta(days=1),
        fecha_hasta=datetime.now(timezone.utc)+timedelta(days=1),
        causa_documentada='Error de calibracion documentado para validar concurrencia',
        parametros_correctos={'offset':0,'ganancia':1})
    barrera=Barrier(2,timeout=20)
    class ContextoCoordinado(ContextoCalidadM09RF60Adapter):
        primera=True
        def bloquear_evaluacion(self,identificador):
            if self.primera:
                self.primera=False
                barrera.wait()
            return super().bloquear_evaluacion(identificador)
    def ejecutar():
        with Session(concurrency_engine) as db:
            db.execute(text('SET LOCAL ROLE sgpmp_app'))
            with como_sistema(db):
                motor=caso(db)
                # M09 usa parámetros de prueba en este caso de concurrencia;
                # motor, locks, repositorios y transacción son reales.
                uc=SolicitarReevaluacionUseCase(db,motor.calidad_repo,motor.telemetria_repo,
                    motor.parametros_port,motor.auditoria_repo,ContextoCoordinado(db),motor.alertas_calidad)
                return uc.execute(solicitud,1,'Prueba de concurrencia')
    with ThreadPoolExecutor(max_workers=2) as pool:
        futuros=[pool.submit(ejecutar) for _ in range(2)]
        resultados=[f.result(timeout=40) for f in futuros]
    assert all(r.evaluaciones_creadas==r.evaluaciones_superadas==2 for r in resultados)
    with Session(concurrency_engine) as db:
        for identificador in (ids1[-1],ids2[-1]):
            filas=db.execute(text('SELECT id_evaluacion,id_evaluacion_superada,estado_evaluacion FROM modulo3.telemetria_calidad WHERE id_telemetria=:id'),{'id':identificador}).all()
            assert len(filas)==3
            assert sum(r[2]=='VIGENTE' for r in filas)==1
            assert len({r[1] for r in filas if r[1] is not None})==2
        assert db.execute(text("SELECT count(*) FROM modulo3.bitacora_auditoria_iot WHERE tipo_evento='REEVALUACION_CALIDAD_SOLICITADA'")).scalar_one()==2

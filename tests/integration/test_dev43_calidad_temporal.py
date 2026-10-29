# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-43 RF-62: PostgreSQL temporal, alertas y permisos |
# | 2026-10-26 | Leandro | INC-M03-104-G165 RF-62: conservar calidad y evidencia del drift con severidad pendiente. |
"""PostgreSQL aislado, triggers activos y JWT/RBAC reales; sin broker MQTT."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,text

from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import ServiceUnavailableError
from src.telemetry.application.use_cases.calidad.evaluar_calidad_telemetria_use_case import EvaluarCalidadTelemetriaUseCase
from src.telemetry.application.use_cases.calidad.generar_alerta_calidad_use_case import GenerarAlertaCalidadUseCase
from src.telemetry.domain.repositories.contexto_calidad_port import ContextoCalidad,LimitesFisicosCalidad
from src.telemetry.domain.repositories.parametros_calidad_port import ParametrosCalidad
from src.telemetry.infrastructure.adapters.contexto_calidad_m09_rf60_adapter import ContextoCalidadM09RF60Adapter
from src.telemetry.infrastructure.repositories.alerta_repository import SqlAlchemyAlertaRepository
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import SqlAlchemyBitacoraAuditoriaIotRepository
from src.telemetry.infrastructure.repositories.telemetria_calidad_repository import SqlAlchemyTelemetriaCalidadRepository
from src.telemetry.infrastructure.repositories.telemetria_repository import SqlAlchemyTelemetriaRepository
from src.telemetry.infrastructure.repositories.postcommit_repository import unidad_postcommit
from src.telemetry.infrastructure.routers import infraestructura_iot_router,alerta_router,calidad_router

_spec=importlib.util.spec_from_file_location('dev43_base_dev05',Path(__file__).with_name('test_dev05_ingesta_bplus_postcommit.py'))
h=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(h)
modelos=h.modelos
equipo=h.equipo
parametros_rf62=h.parametros_rf62
pytestmark=pytest.mark.integration


def serie(db,equipo,*,congelado=False,gap=1,estado='LECTURA_VALIDA'):
    captura=datetime.now(timezone.utc)-timedelta(minutes=1)
    ids=[]
    for i in range(21):
        momento=captura-timedelta(minutes=(20-i)+(gap-1 if i<20 else 0))
        ids.append(db.execute(text('''INSERT INTO modulo3.telemetrias(id_sensor,id_variable,
            id_dispositivo_iot,valor_crudo,valor_ajustado,timestamp_captura,timestamp_procesamiento,
            origen,estado_calidad,calibrado,categoria_variable,unidad_medida,valor_agregado,tipo_dato,metadatos,
            frecuencia_muestreo_min) VALUES (:s,9,:d,:v,:v,:ts,now(),'TIEMPO_REAL',
            CAST(:estado AS modulo3.enum_telemetria_estado_calidad),true,'AMBIENTAL','°C',false,'CRUDO','{}',5)
            RETURNING id_telemetria'''),
            dict(s=equipo['sensor'],d=equipo['device'],v=22 if congelado else 22+i%2,
                 ts=momento,estado=estado if i==20 else 'LECTURA_VALIDA')).scalar_one())
    db.commit()
    return ids,captura


def caso(db,*,contexto=None,alertas=None,auditoria=None):
    return EvaluarCalidadTelemetriaUseCase(db,SqlAlchemyTelemetriaRepository(db),
        SqlAlchemyTelemetriaCalidadRepository(db),
        SimpleNamespace(obtener_parametros=lambda *a:ParametrosCalidad()),
        auditoria if auditoria is not None else SqlAlchemyBitacoraAuditoriaIotRepository(db),
        contexto_port=contexto if contexto is not None else ContextoCalidadM09RF60Adapter(db),
        alertas_calidad=alertas if alertas is not None else GenerarAlertaCalidadUseCase(SqlAlchemyAlertaRepository(db)))


def evaluar(uc,equipo,ids,ts,**kw):
    return uc.execute(ids[-1],equipo['sensor'],9,Decimal(22),Decimal(22),ts,
                      kw.pop('estado','LECTURA_VALIDA'),kw.pop('calibracion',None),**kw)


def periodo(db,equipo,inicio,fin=None,*,sensores=None,estado='INACTIVO'):
    db.execute(text('''INSERT INTO modulo3.periodos_inactividad(id_dispositivo_iot,sensores_afectados,
        fecha_inicio,fecha_fin,estado_durante_periodo,causa_primaria,caso_diagnosticado,buffer_activo_durante)
        VALUES (:d,:sensores,:inicio,:fin,CAST(:estado AS modulo3.enum_estado_dispositivo),
            'FALLO_CONECTIVIDAD','{}',false)'''),
        dict(d=equipo['device'],sensores=sensores or [],inicio=inicio,fin=fin,estado=estado))
    db.commit()


def alertas(db,equipo):
    return db.execute(text('SELECT * FROM modulo3.alertas WHERE id_sensor=:s ORDER BY id_alerta'),
                      {'s':equipo['sensor']}).mappings().all()


@pytest.mark.parametrize('gap,esperado',[(9,False),(10,False),(11,True)])
def test_gap_real_y_snapshot_original_inmutable(db_session,equipo,gap,esperado):
    ids,ts=serie(db_session,equipo,gap=gap)
    antes=db_session.execute(text('SELECT jsonb_agg(to_jsonb(t) ORDER BY id_telemetria) FROM modulo3.telemetrias t WHERE id_sensor=:s'),{'s':equipo['sensor']}).scalar_one()
    ev=evaluar(caso(db_session),equipo,ids,ts)
    assert ('gap_temporal_anomalo' in ev.flags_detectados) is esperado
    assert ev.indice_calidad==(90 if esperado else 100)
    assert db_session.execute(text('SELECT jsonb_agg(to_jsonb(t) ORDER BY id_telemetria) FROM modulo3.telemetrias t WHERE id_sensor=:s'),{'s':equipo['sensor']}).scalar_one()==antes


def test_serie_inactiva_omite_sin_calificacion_y_sin_duplicar_bitacora(db_session,equipo):
    ids,ts=serie(db_session,equipo,congelado=True)
    periodo(db_session,equipo,ts-timedelta(minutes=30))
    for _ in range(2):assert evaluar(caso(db_session),equipo,ids,ts) is None
    assert db_session.execute(text('SELECT count(*) FROM modulo3.telemetria_calidad WHERE id_telemetria=:id'),{'id':ids[-1]}).scalar_one()==0
    eventos=db_session.execute(text("SELECT accion_detallada,hash_integridad FROM modulo3.bitacora_auditoria_iot WHERE entidad_afectada_id=:id AND tipo_evento='EVALUACION_OMITIDA_POR_INACTIVIDAD'"),{'id':str(ids[-1])}).all()
    assert len(eventos)==1 and eventos[0][0]['flags']=={} and len(eventos[0][1])==64
    assert alertas(db_session,equipo)==[]


def test_omision_no_bloquea_finalizacion_postcommit(db_session,equipo,parametros_rf62):
    ids,ts=serie(db_session,equipo)
    periodo(db_session,equipo,ts-timedelta(minutes=30))
    p=h.procesador(db_session)
    p.execute()
    eventos=h.evidencias(db_session,ids[-1])
    assert any(e['tipo_evento']=='POSTCOMMIT_RF62_COMPLETADO' for e in eventos)
    assert not any(e['tipo_evento']=='POSTCOMMIT_RF62_FALLIDO' for e in eventos)


def test_solapamiento_parcial_no_se_resuelve_por_supuestos(db_session,equipo):
    ids,ts=serie(db_session,equipo,gap=20)
    periodo(db_session,equipo,ts-timedelta(minutes=15),ts-timedelta(minutes=5))
    with pytest.raises(ServiceUnavailableError,match='parcialmente'):
        evaluar(caso(db_session),equipo,ids,ts)
    assert SqlAlchemyTelemetriaCalidadRepository(db_session).obtener_por_lectura(ids[-1]) is None


def test_inactividad_de_otro_sensor_no_excluye(db_session,equipo):
    ids,ts=serie(db_session,equipo,gap=11)
    periodo(db_session,equipo,ts-timedelta(minutes=30),sensores=[equipo['sensor']+9999])
    assert evaluar(caso(db_session),equipo,ids,ts).flags_detectados['gap_temporal_anomalo']['activo']


def test_serie_mixta_excluye_lecturas_inactivas_sin_falso_congelamiento(db_session,equipo):
    ids,ts=serie(db_session,equipo,congelado=True)
    periodo(db_session,equipo,ts-timedelta(minutes=12),ts-timedelta(minutes=6))
    ev=evaluar(caso(db_session),equipo,ids,ts)
    assert ev.clasificacion_calidad.value=='INDETERMINADA'
    assert 'sensor_congelado' not in ev.flags_detectados
    assert alertas(db_session,equipo)==[]


def test_limites_actuales_no_reciben_version_artificial(db_session,equipo):
    ids,ts=serie(db_session,equipo)
    ev=evaluar(caso(db_session),equipo,ids,ts)
    assert ev.version_limites_fisicos_aplicada is None
    assert ev.parametros_aplicados['limites_fisicos']['estado']=='PENDIENTE_VERSIONADO_M09'


def test_recupera_n_validas_tras_excluir_periodos(db_session,equipo):
    ids,ts=serie(db_session,equipo)
    # Antecedentes activos suficientes, anteriores a la ventana inicial.
    for i in range(20):
        db_session.execute(text('''INSERT INTO modulo3.telemetrias(id_sensor,id_variable,id_dispositivo_iot,
            valor_crudo,valor_ajustado,timestamp_captura,timestamp_procesamiento,origen,estado_calidad,
            calibrado,categoria_variable,unidad_medida,valor_agregado,tipo_dato,metadatos)
            VALUES (:s,9,:d,:v,:v,:ts,now(),'TIEMPO_REAL','LECTURA_VALIDA',true,'AMBIENTAL','°C',false,'CRUDO','{}')'''),
            dict(s=equipo['sensor'],d=equipo['device'],v=22+i%2,ts=ts-timedelta(minutes=21+i)))
    db_session.commit()
    periodo(db_session,equipo,ts-timedelta(minutes=12),ts-timedelta(minutes=6))
    ev=evaluar(caso(db_session),equipo,ids,ts)
    assert ev.clasificacion_calidad.value=='APTO'
    assert ev.parametros_aplicados['consistencia_temporal']['lecturas_excluidas_rf60']==7


def test_rechazo_por_historial_sin_inicio_no_crea_calidad(db_session,equipo):
    ids,ts=serie(db_session,equipo)
    periodo(db_session,equipo,None)
    with pytest.raises(ServiceUnavailableError,match='sin inicio'):
        evaluar(caso(db_session),equipo,ids,ts)
    assert SqlAlchemyTelemetriaCalidadRepository(db_session).obtener_por_lectura(ids[-1]) is None


def test_versiones_se_persisten_en_cadena_con_proveedor_versionado_explicito(db_session,equipo):
    ids,ts=serie(db_session,equipo)
    class ProveedorDePrueba(ContextoCalidadM09RF60Adapter):
        version='V1'
        def obtener(self,*args):
            c=super().obtener(*args)
            return ContextoCalidad(c.lecturas,c.periodos,c.frecuencia_muestreo_min,
                LimitesFisicosCalidad(Decimal(0),Decimal(100),self.version,'proveedor_versionado_de_prueba'))
    port=ProveedorDePrueba(db_session)
    primero=evaluar(caso(db_session,contexto=port),equipo,ids,ts)
    port.version='V2'
    segundo=evaluar(caso(db_session,contexto=port),equipo,ids,ts)
    assert segundo.version_limites_fisicos_aplicada=='V2'
    assert segundo.id_evaluacion_superada==primero.id_evaluacion
    assert db_session.execute(text('SELECT version_limites_fisicos_aplicada FROM modulo3.telemetria_calidad WHERE id_evaluacion=:id'),{'id':primero.id_evaluacion}).scalar_one()=='V1'


def test_congelado_alerta_tecnica_historial_unico_y_reintento(db_session,equipo):
    ids,ts=serie(db_session,equipo,congelado=True)
    evaluar(caso(db_session),equipo,ids,ts)
    evaluar(caso(db_session),equipo,ids,ts)
    filas=alertas(db_session,equipo)
    assert len(filas)==1 and filas[0]['tipo_alerta']=='TECNICA'
    assert filas[0]['estado_alerta']=='ACTIVA' and filas[0]['severidad']=='CRITICO'
    assert filas[0]['frecuencia_evento']==1
    assert db_session.execute(text('SELECT count(*) FROM modulo3.historico_estados_alertas WHERE id_alerta=:id'),{'id':filas[0]['id_alerta']}).scalar_one()==1


def test_fallo_despues_de_insertar_alerta_revierte_todo(db_session,equipo):
    ids,ts=serie(db_session,equipo,congelado=True)
    class Falla(GenerarAlertaCalidadUseCase):
        def execute(self,ev):
            super().execute(ev)
            raise RuntimeError('fallo después de alerta')
    with pytest.raises(RuntimeError):evaluar(caso(db_session,alertas=Falla(SqlAlchemyAlertaRepository(db_session))),equipo,ids,ts)
    assert alertas(db_session,equipo)==[]
    assert SqlAlchemyTelemetriaCalidadRepository(db_session).obtener_por_lectura(ids[-1]) is None
    evaluar(caso(db_session),equipo,ids,ts)
    assert len(alertas(db_session,equipo))==1


def test_drift_significativo_sin_severidad_conserva_calidad_y_pendiente(db_session,equipo):
    ids,ts=serie(db_session,equipo)
    ev=evaluar(caso(db_session),equipo,ids,ts,calibracion={'ganancia':2,'offset':0})
    assert ev.flags_detectados['posible_drift']['activo'] is True
    assert SqlAlchemyTelemetriaCalidadRepository(db_session).obtener_por_lectura(ids[-1]).id_evaluacion==ev.id_evaluacion
    assert alertas(db_session,equipo)==[]
    evento=db_session.execute(text("""SELECT resultado,accion_detallada FROM modulo3.bitacora_auditoria_iot
        WHERE entidad_afectada_id=:id AND tipo_evento='EVALUACION_CALIDAD_COMPLETADA'"""),
        {'id':str(ids[-1])}).one()
    assert evento[0]=='PARCIAL'
    assert evento[1]['notificaciones_pendientes'][0]['motivo']=='SEVERIDAD_DRIFT_NO_CONFIGURADA'


@pytest.fixture
def api(db_session,monkeypatch):
    from src.shared import jwt
    monkeypatch.setattr(jwt,'_SECRET_KEY','sgpmp-integration-tests-only')
    app=FastAPI();register_error_handlers(app)
    for router in (infraestructura_iot_router.router,alerta_router.router,calidad_router.router):app.include_router(router)
    def sesion():
        db_session.info.clear()
        yield db_session
    app.dependency_overrides[get_db]=sesion
    with TestClient(app,raise_server_exceptions=False) as client:yield client


@pytest.mark.parametrize('rol,permitido',[('Productor',False),('Ingeniero de Campo',True)])
def test_rbac_real_y_aislamiento_operativo(api,db_session,equipo,crear_usuario_db,crear_auth_headers,rol,permitido):
    ids,ts=serie(db_session,equipo,congelado=True)
    evaluar(caso(db_session),equipo,ids,ts)
    alerta=alertas(db_session,equipo)[0]
    id_rol=db_session.execute(text('SELECT id_rol FROM modulo1.roles WHERE nombre_rol=:rol'),{'rol':rol}).scalar_one()
    usuario=crear_usuario_db(id_rol=id_rol)
    finca=db_session.execute(text('SELECT id_finca FROM modulo9.infraestructuras WHERE id_infraestructura=:id'),{'id':equipo['area']}).scalar_one()
    db_session.execute(text('INSERT INTO modulo9.usuarios_fincas(id_usuario,id_finca,es_activo) VALUES (:u,:f,true)'),{'u':usuario['id_usuario'],'f':finca})
    headers=crear_auth_headers(usuario)
    r=api.get('/iot/alertas-tecnicas',headers=headers)
    assert r.status_code==(200 if permitido else 403),r.text
    if permitido:assert any(a['id_alerta']==alerta['id_alerta'] for a in r.json()['items'])
    else:
        operativo=api.get('/iot/alertas',headers=headers)
        assert operativo.status_code==200,operativo.text
        assert all(a['id_alerta']!=alerta['id_alerta'] for a in operativo.json()['items'])
        assert api.get(f"/iot/alertas/{alerta['id_alerta']}",headers=headers).status_code==404


def test_ingeniero_fuera_de_finca_no_lista_ni_modifica(api,db_session,equipo,crear_usuario_db,crear_auth_headers):
    ids,ts=serie(db_session,equipo,congelado=True)
    evaluar(caso(db_session),equipo,ids,ts)
    alerta=alertas(db_session,equipo)[0]
    rol=db_session.execute(text("SELECT id_rol FROM modulo1.roles WHERE nombre_rol='Ingeniero de Campo'")).scalar_one()
    usuario=crear_usuario_db(id_rol=rol);headers=crear_auth_headers(usuario)
    r=api.get('/iot/alertas-tecnicas',headers=headers)
    assert r.status_code==200 and r.json()['total']==0,r.text
    r=api.patch(f"/iot/alertas-tecnicas/{alerta['id_alerta']}/estado",headers=headers,json={'nuevo_estado':'EN_ATENCION'})
    assert r.status_code==404,r.text
    assert alertas(db_session,equipo)[0]['estado_alerta']=='ACTIVA'


def test_sin_autenticacion_se_rechaza(api):
    assert api.get('/iot/alertas-tecnicas').status_code==401


def test_http_e5_responde_200_sin_falsa_evaluacion(api,db_session,equipo,parametros_rf62,crear_usuario_db,crear_auth_headers):
    ids,ts=serie(db_session,equipo)
    periodo(db_session,equipo,ts-timedelta(minutes=30))
    rol=db_session.execute(text("SELECT id_rol FROM modulo1.roles WHERE es_protegido")).scalar_one()
    headers=crear_auth_headers(crear_usuario_db(id_rol=rol))
    r=api.post(f'/iot/calidad/{ids[-1]}/evaluar',headers=headers)
    assert r.status_code==200,r.text
    assert r.json()=={'id_telemetria':ids[-1],'resultado':'EVALUACION_OMITIDA_POR_INACTIVIDAD'}


@pytest.fixture
def concurrency_engine(integration_engine,tmp_path):
    # Las filas inmutables confirmadas no pueden borrarse al final de una prueba.
    # Se aísla la prueba en otra BD para no alimentar el worker de otros casos.
    nombre='dev43_concurrency_test_'+uuid4().hex
    admin=create_engine(integration_engine.url.set(database='postgres'),isolation_level='AUTOCOMMIT')
    motor=None
    with admin.connect() as c:
        c.exec_driver_sql(f'CREATE DATABASE "{nombre}"')
    try:
        url=integration_engine.url.set(database=nombre)
        env=dict(os.environ,DATABASE_URL=url.render_as_string(hide_password=False),
                 ALEMBIC_DATABASE_URL=url.render_as_string(hide_password=False))
        log=tmp_path/'migraciones_concurrencia.log'
        with log.open('w',encoding='utf-8') as salida:
            resultado=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],env=env,
                stdout=salida,stderr=subprocess.STDOUT,timeout=180)
        assert resultado.returncode==0,log.read_text(encoding='utf-8')[-3000:]
        motor=create_engine(url,use_insertmanyvalues=False)
        yield motor
    finally:
        if motor is not None:motor.dispose()
        with admin.connect() as c:c.exec_driver_sql(f'DROP DATABASE "{nombre}"')
        admin.dispose()


def test_concurrencia_calidad_cadena_y_alerta_unicas(concurrency_engine):
    # Commit real solo en la base aislada: dos conexiones deben ver el setup.
    with unidad_postcommit(concurrency_engine,identidad=False) as u:
        equipo=h.hardware(u.db)
        ids,ts=serie(u.db,equipo,congelado=True)
        u.confirmar()
    def ejecutar():
        with unidad_postcommit(concurrency_engine,identidad=False) as u:
            resultado=evaluar(caso(u.db),equipo,ids,ts)
            u.confirmar()
            return resultado.id_evaluacion
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados=list(pool.map(lambda _:ejecutar(),range(2)))
    assert len(set(resultados))==2
    with unidad_postcommit(concurrency_engine,identidad=False) as u:
        assert len(alertas(u.db,equipo))==1
        filas=u.db.execute(text('SELECT estado_evaluacion,id_evaluacion_superada FROM modulo3.telemetria_calidad WHERE id_telemetria=:id'),{'id':ids[-1]}).all()
        assert len(filas)==2
        assert sum(f[0]=='VIGENTE' for f in filas)==1
        assert sum(f[1] is not None for f in filas)==1

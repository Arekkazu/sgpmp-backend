# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-28 RF-53/62: verifica PostgreSQL, recuperacion y concurrencia de vision |
# | 2026-10-25 | Arekkazu | INC-M03-134-G192 RF-62: sobre normativo persistido y calidad evaluada aparte |
"""PostgreSQL real aislado con las migraciones del repositorio (DB-09 y 8c4e2a6f1b93)."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.configuracion_global.configurar_parametros_mlops_use_case import ConfigurarParametrosMLOpsUseCase
from src.configuration.domain.entities.parametros_vision import PREDETERMINADOS_VISION
from src.configuration.domain.entities.parametros_heartbeat import VENTANAS, COBERTURA, DURACION
from src.configuration.infrastructure.repositories.configuracion_global_repository import SqlAlchemyConfiguracionGlobalRepository
from src.prediction.infrastructure.repositories.parametros_mlops_repository import SqlAlchemyParametrosMLOpsRepository
from src.shared.errors import ValidationError
from src.telemetry.application.use_cases.calidad.evaluar_calidad_vision_use_case import EvaluarCalidadVisionUseCase
from src.telemetry.infrastructure.adapters.dispositivo_m09_adapter import DispositivoM09Adapter
from src.telemetry.infrastructure.repositories.observacion_vision_repository import SqlAlchemyObservacionVisionRepository
from src.telemetry.infrastructure.adapters.parametros_vision_mlops_adapter import ParametrosVisionMLOpsAdapter
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import SqlAlchemyBitacoraAuditoriaIotRepository
from src.telemetry.infrastructure.workers.postcommit_worker import construir_procesador

_spec=importlib.util.spec_from_file_location('dev28_vision_base',Path(__file__).with_name('test_dev07_vision_d4.py'))
h=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h)
modelos, equipo, client = h.modelos, h.equipo, h.client
pytestmark=pytest.mark.integration


def configurar(db):
    usuario=db.execute(text('SELECT min(id_usuario) FROM modulo1.usuarios')).scalar_one()
    repo=SqlAlchemyParametrosMLOpsRepository(db)
    writer=ConfigurarParametrosMLOpsUseCase(db,repo,SqlAlchemyConfiguracionGlobalRepository(db))
    # Solo datos de prueba autorizados. No inicializa RF-18 ni modifica tiempos de heartbeat.
    writer.execute(PREDETERMINADOS_VISION,usuario)
    writer.execute({VENTANAS:3,COBERTURA:.30,DURACION:60},usuario)
    return writer,usuario


@pytest.fixture
def politica(db_session):
    return configurar(db_session)


def normativo(equipo):
    datos=h.sobre(equipo)
    datos.update(tipo_dato='VECTOR_COMPORTAMIENTO',n_individuos_observados=0,origen='TIEMPO_REAL')
    datos['calidad']['estado_calibracion']='CALIBRADO'
    datos['calidad'].pop('n_tracks')
    return datos


def guardar(db,equipo,inicio, cobertura=.1):
    datos=h.sobre(equipo,ventana_inicio=inicio.isoformat(),ventana_fin=(inicio+timedelta(seconds=60)).isoformat())
    datos['calidad']['cobertura_ventana']=cobertura
    dto=h.ObservacionVisionD4DTO(**datos)
    h.IngerirObservacionesVisionUseCase(db,h.SqlAlchemyObservacionVisionRepository(db),h.DispositivoM09Adapter(db)).execute(dto)
    return h.filas(db,equipo)[-1]['id_observacion_vision']


def ventanas(db,equipo,coberturas=(.1,.1,.1)):
    inicio=(datetime.now(timezone.utc)-timedelta(minutes=10)).replace(microsecond=0)
    return [guardar(db,equipo,inicio+timedelta(seconds=60*i),c) for i,c in enumerate(coberturas)]


def eventos(db,equipo,tipo='SIN_DETECCION_VALIDA'):
    return db.execute(text('''SELECT tipo_evento,entidad_afectada_id,accion_detallada,hash_integridad
        FROM modulo3.bitacora_auditoria_iot WHERE tipo_evento=:t
        AND accion_detallada->>'id_dispositivo_iot'=:id'''),{'t':tipo,'id':str(equipo['device'])}).mappings().all()


def test_contrato_normativo_se_persiste_y_queda_pendiente_de_rf62(client,db_session,equipo):
    datos=normativo(equipo)
    r=h.enviar(client,datos)
    assert r.status_code==201,r.text
    assert r.json()['observaciones'][0]['indice_calidad_vision'] is None
    fila=h.filas(db_session,equipo)[0]
    assert (fila['n_individuos_observados'],fila['origen'],fila['cantidad_tracks'])==(0,'TIEMPO_REAL',None)
    assert fila['estado_calibracion']=='CALIBRADO' and fila['fecha_evaluacion_calidad'] is None
    schema=client.get('/openapi.json').json()['components']['schemas']['ObservacionVisionD4DTO']
    assert {'tipo_dato','n_individuos_observados','origen'}<=set(schema['required'])
    assert schema['additionalProperties'] is False


@pytest.mark.parametrize('campo',['tipo_dato','n_individuos_observados','origen'])
def test_normativo_incompleto_es_400_sin_persistencia(client,db_session,equipo,campo):
    datos=normativo(equipo);datos.pop(campo)
    r=h.enviar(client,datos)
    assert r.status_code==400,r.text
    assert not h.filas(db_session,equipo)


def test_pesos_persistidos_aplican_sin_reinicio_y_lo_evaluado_no_cambia(client,db_session,equipo,politica):
    writer,usuario=politica
    uc=EvaluarCalidadVisionUseCase(db_session,SqlAlchemyObservacionVisionRepository(db_session),
        ParametrosVisionMLOpsAdapter(SqlAlchemyParametrosMLOpsRepository(db_session)),DispositivoM09Adapter(db_session))
    assert h.enviar(client,normativo(equipo)).status_code==201
    primera=h.filas(db_session,equipo)[0]['id_observacion_vision']
    # 100 × (0.40×0.95 + 0.35×min(1,24/fps) + 0.25×(1 − 1/5)) con fps=25
    evaluada=uc.execute(primera)
    assert evaluada.indice_calidad_vision==Decimal('91.60') and evaluada.clasificacion_calidad=='OPTIMA'
    writer.execute({'w1':1,'w2':0,'w3':0,'umbral_optima':96},usuario)
    datos=normativo(equipo)
    fin=datetime.fromisoformat(datos['ventana_fin'])+timedelta(minutes=1)
    datos.update(ventana_inicio=(fin-timedelta(minutes=1)).isoformat(),ventana_fin=fin.isoformat())
    assert h.enviar(client,datos).status_code==201
    segunda=uc.execute(h.filas(db_session,equipo)[1]['id_observacion_vision'])
    assert segunda.indice_calidad_vision==95 and segunda.clasificacion_calidad=='DEGRADADA'
    assert segunda.es_apto_para_ia and segunda.es_confianza_baja and not segunda.es_apto_para_nic41
    # Idempotente: la primera conserva el índice de los parámetros con que se evaluó.
    assert uc.execute(primera).indice_calidad_vision==Decimal('91.60')
    fila=h.filas(db_session,equipo)[0]
    assert fila['indice_calidad_vision']==Decimal('91.60') and fila['clasificacion_calidad']=='OPTIMA'
    assert set(fila['json_flags_detectados'])=={'cobertura_baja','tracking_inestable','fps_insuficiente','sin_linea_base'}


def test_politica_invalida_no_persiste_pesos_parciales(db_session,politica):
    writer,usuario=politica
    with pytest.raises(ValidationError):
        writer.execute({'w1':.8},usuario)
    pesos=SqlAlchemyParametrosMLOpsRepository(db_session).obtener(['w1','w2','w3'])
    assert [pesos[n].valor for n in ('w1','w2','w3')]==[.4,.35,.25]


def test_postcommit_persiste_diagnostico_sin_alerta_y_es_idempotente(client,db_session,equipo,politica):
    inicio=(datetime.now(timezone.utc)-timedelta(minutes=10)).replace(microsecond=0)
    ids=[]
    for i in range(3):
        datos=h.sobre(equipo,ventana_inicio=(inicio+timedelta(minutes=i)).isoformat(),
            ventana_fin=(inicio+timedelta(minutes=i+1)).isoformat())
        datos['calidad']['cobertura_ventana']=.1
        r=h.enviar(client,datos)
        assert r.status_code==201,r.text
        ids.append(r.json()['observaciones'][0]['id_observacion_vision'])
    originales=[dict(f) for f in h.filas(db_session,equipo)]
    assert not eventos(db_session,equipo)
    worker=construir_procesador(db_session.get_bind(),identidad=False)
    # 3 de VISION_CALIDAD (RF-62) + 3 de VISION_DETECCION.
    assert worker.execute()=={'completados':6,'fallidos':0}
    assert worker.execute()=={'completados':0,'fallidos':0}
    evidencia=eventos(db_session,equipo)
    assert len(evidencia)==1 and evidencia[0]['entidad_afectada_id']==str(ids[-1])
    assert evidencia[0]['accion_detallada']['ventanas']==ids
    assert evidencia[0]['hash_integridad']
    # RF-62 solo llena el bloque de calidad; el dato observado no cambia.
    evaluacion={'indice_calidad_vision','clasificacion_calidad','es_apto_para_ia','es_confianza_baja',
        'json_flags_detectados','fecha_evaluacion_calidad'}
    despues=[dict(f) for f in h.filas(db_session,equipo)]
    assert [{k:v for k,v in f.items() if k not in evaluacion} for f in despues]==\
        [{k:v for k,v in f.items() if k not in evaluacion} for f in originales]
    # 100 × (0.40×0.1 + 0.35×24/25 + 0.25×(1 − 1/5)) = 4 + 33.6 + 20
    assert [(f['indice_calidad_vision'],f['clasificacion_calidad']) for f in despues]==[(Decimal('57.60'),'DEGRADADA')]*3
    assert db_session.execute(text('SELECT count(*) FROM modulo3.alertas WHERE id_dispositivo_ioit=:id'),{'id':equipo['device']}).scalar_one()==0


@pytest.mark.parametrize('coberturas',[(.1,.1),(.1,.3,.1),(.1,.8,.1)])
def test_ventana_valida_o_serie_corta_no_diagnostica(db_session,equipo,politica,coberturas):
    ventanas(db_session,equipo,coberturas)
    assert construir_procesador(db_session.get_bind(),identidad=False).execute()['fallidos']==0
    assert not eventos(db_session,equipo)


def test_brecha_y_camaras_no_se_mezclan(db_session,equipo,politica):
    otra=h.hardware(db_session)
    inicio=datetime.now(timezone.utc)-timedelta(minutes=10)
    guardar(db_session,equipo,inicio)
    guardar(db_session,otra,inicio+timedelta(minutes=1))
    guardar(db_session,equipo,inicio+timedelta(minutes=2))
    construir_procesador(db_session.get_bind(),identidad=False).execute()
    assert not eventos(db_session,equipo) and not eventos(db_session,otra)


def test_llegada_fuera_de_orden_completa_ventana_actual(db_session,equipo,politica):
    inicio=datetime.now(timezone.utc)-timedelta(minutes=10)
    guardar(db_session,equipo,inicio)
    ultima=guardar(db_session,equipo,inicio+timedelta(minutes=2))
    worker=construir_procesador(db_session.get_bind(),identidad=False)
    worker.execute()
    assert not eventos(db_session,equipo)
    guardar(db_session,equipo,inicio+timedelta(minutes=1))
    worker.execute()
    assert [e['entidad_afectada_id'] for e in eventos(db_session,equipo)]==[str(ultima)]


def test_parametros_de_ventanas_cambian_en_mismo_worker(db_session,equipo,politica):
    writer,usuario=politica
    writer.execute({VENTANAS:4},usuario)
    ids=ventanas(db_session,equipo)
    worker=construir_procesador(db_session.get_bind(),identidad=False)
    worker.execute()
    assert not eventos(db_session,equipo)
    writer.execute({VENTANAS:2},usuario)
    fin=h.filas(db_session,equipo)[-1]['fecha_observacion']
    nueva=guardar(db_session,equipo,fin)
    worker.execute()
    assert eventos(db_session,equipo)[0]['accion_detallada']['ventanas']==[ids[-1],nueva]


def test_configuracion_ausente_preserva_dato_y_permite_reintento(db_session,equipo):
    ventanas(db_session,equipo)
    worker=construir_procesador(db_session.get_bind(),identidad=False,reintento_seg=1)
    # Sin política fallan las dos etapas de visión (RF-62 y detección) por cada ventana.
    assert worker.execute()=={'completados':0,'fallidos':6}
    assert len(h.filas(db_session,equipo))==3 and not eventos(db_session,equipo)
    assert all(f['fecha_evaluacion_calidad'] is None for f in h.filas(db_session,equipo))
    configurar(db_session)
    time.sleep(1.1)
    assert worker.execute()=={'completados':6,'fallidos':0}
    assert len(eventos(db_session,equipo))==1


def test_error_de_evidencia_revierte_diagnostico_y_recupera(db_session,equipo,politica,monkeypatch):
    ventanas(db_session,equipo)
    original=SqlAlchemyBitacoraAuditoriaIotRepository.registrar
    def fallar(repo,evento):
        resultado=original(repo,evento)
        if evento.tipo_evento=='POSTCOMMIT_VISION_DETECCION_COMPLETADO':
            raise RuntimeError('fallo de prueba posterior al diagnostico')
        return resultado
    worker=construir_procesador(db_session.get_bind(),identidad=False,reintento_seg=1)
    with monkeypatch.context() as m:
        m.setattr(SqlAlchemyBitacoraAuditoriaIotRepository,'registrar',fallar)
        assert worker.execute()['fallidos']==3
    assert not eventos(db_session,equipo) and len(h.filas(db_session,equipo))==3
    time.sleep(1.1)
    assert worker.execute()['fallidos']==0
    assert len(eventos(db_session,equipo))==1


def test_workers_concurrentes_no_duplican_diagnostico(motor_vision_concurrente):
    with Session(motor_vision_concurrente) as db:
        configurar(db);equipo=h.hardware(db);ventanas(db,equipo)
    def ejecutar(_):
        return construir_procesador(motor_vision_concurrente,identidad=False).execute()
    with ThreadPoolExecutor(max_workers=2) as executor:
        resultados=list(executor.map(ejecutar,range(2)))
    assert sum(r['fallidos'] for r in resultados)==0
    with Session(motor_vision_concurrente) as db:
        assert len(eventos(db,equipo))==1
        assert len(h.filas(db,equipo))==3


def test_script_siembra_vision_idempotente_y_conserva_valores(motor_vision_concurrente):
    motor=motor_vision_concurrente
    with motor.connect() as c:
        usuario=c.execute(text('''SELECT u.id_usuario FROM modulo1.usuarios u JOIN modulo1.roles r USING(id_rol)
            WHERE lower(r.nombre_rol)='administrador' ORDER BY u.id_usuario LIMIT 1''')).scalar_one()
    raiz=Path(__file__).resolve().parents[2]
    env=os.environ|{'DEV14_DATABASE_URL':motor.url.render_as_string(hide_password=False)}
    def ejecutar(*args):
        r=subprocess.run([sys.executable,'scripts/configurar_parametros_dev14.py','--sembrar-vision',
            '--id-usuario',str(usuario),*args],cwd=raiz,env=env,capture_output=True,text=True,timeout=60)
        assert r.returncode==0,r.stdout+r.stderr
        return r.stdout
    assert 'Simulación' in ejecutar()
    with motor.connect() as c:
        assert c.execute(text("SELECT count(*) FROM modulo4.parametros_mlops WHERE nombre_parametro='w1'")).scalar_one()==0
    assert 'w1: creado' in ejecutar('--aplicar')
    with Session(motor) as db:
        writer,responsable=configurar(db)
        writer.execute({'w1':.5,'w2':.25,'w3':.25},responsable)
    assert 'w1: conservado' in ejecutar('--aplicar')
    with Session(motor) as db:
        assert SqlAlchemyParametrosMLOpsRepository(db).obtener(['w1'])['w1'].valor==.5

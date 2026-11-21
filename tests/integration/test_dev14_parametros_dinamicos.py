"""Configuración PostgreSQL real → mismos consumidores sin reinicio.

Los escenarios de cálculo aíslan los puertos de salida con los mismos dobles de
las unitarias. El escenario final usa también persistencia real de telemetría y
calidad, condicionado a DEV-02, que permanece en su rama independiente.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import importlib
import importlib.util
import json
import os
from pathlib import Path
import pkgutil
import subprocess
import sys
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.configuracion_global.configurar_parametros_mlops_use_case import ConfigurarParametrosMLOpsUseCase
from src.configuration.domain.entities.parametro_mlops import RF57_CONFIANZA, RF72_VENTANA
from src.configuration.infrastructure.repositories.configuracion_global_repository import SqlAlchemyConfiguracionGlobalRepository
from src.prediction.infrastructure.repositories.parametros_mlops_repository import SqlAlchemyParametrosMLOpsRepository
from src.shared.errors import BusinessRuleError, ServiceUnavailableError, ValidationError
from src.telemetry.infrastructure.adapters.parametros_calidad_mlops_adapter import ParametrosCalidadMLOpsAdapter

pytestmark=pytest.mark.integration
_spec=importlib.util.spec_from_file_location('dev14_dobles',Path(__file__).parents[1]/'configuration/test_dev14_parametros_dinamicos.py')
h=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h)


@pytest.fixture(autouse=True)
def modelos():
    for paquete in ('src.configuration.infrastructure.models','src.biological_assets.infrastructure.models',
                    'src.prediction.infrastructure.models','src.telemetry.infrastructure.models','src.identity_access.infrastructure.models'):
        mod=importlib.import_module(paquete)
        for item in pkgutil.iter_modules(mod.__path__,paquete+'.'): importlib.import_module(item.name)


@pytest.fixture
def administrador(db_session):
    return db_session.execute(text("SELECT u.id_usuario FROM modulo1.usuarios u JOIN modulo1.roles r ON r.id_rol=u.id_rol WHERE lower(r.nombre_rol)='administrador' ORDER BY u.id_usuario LIMIT 1")).scalar_one()


@pytest.fixture
def configurados(db_session,administrador):
    repo=SqlAlchemyParametrosMLOpsRepository(db_session)
    writer=ConfigurarParametrosMLOpsUseCase(db_session,repo)
    writer.execute({k:p.valor for k,p in h.configuracion().items()},administrador)
    activa=db_session.execute(text('SELECT id_configuracion_global FROM modulo9.configuraciones_globales WHERE es_activo=true')).scalar_one_or_none()
    if activa is None:
        db_session.execute(text('''INSERT INTO modulo9.configuraciones_globales(frecuencia_muestreo,heartbeat,fecha_actualizacion,id_usuario,es_activo)
            VALUES (7,14,now(),:uid,true)'''),{'uid':administrador})
    else:
        db_session.execute(text('UPDATE modulo9.configuraciones_globales SET frecuencia_muestreo=7,heartbeat=14 WHERE id_configuracion_global=:id'),{'id':activa})
    db_session.commit()
    return repo,writer


@pytest.mark.parametrize('nombre,inicial,posterior,serie,calibracion,flag',[
    ('rf62_k',1,4,[19,20,21,22,23,24],None,'outlier_estadistico'),
    ('rf62_m',3,4,[20,20,20,21,22,23],None,'sensor_congelado'),
    ('rf62_umbral_drift',5,20,[20,20.5,21,21.5,22,22.5],{'ganancia':1.2,'offset':0},'posible_drift'),
    ('rf62_p',3,6,[20,20.5,21,21.5,22,22.5],{'ganancia':1.05,'offset':0},'posible_drift'),
])
def test_rf62_valor_persistido_cambia_calculo_sin_recrear_consumidor(db_session,administrador,configurados,nombre,inicial,posterior,serie,calibracion,flag):
    repo,writer=configurados
    writer.execute({nombre:inicial}|({'rf62_umbral_drift':1} if nombre=='rf62_p' else {}),administrador)
    uc=h.calidad_use_case(db_session,repo,SqlAlchemyConfiguracionGlobalRepository(db_session),[Decimal(str(v)) for v in serie])
    primero=h.evaluar(uc,calibracion=calibracion)
    assert primero.flags_detectados[flag]['activo']
    writer.execute({nombre:posterior},administrador)
    segundo=h.evaluar(uc,calibracion=calibracion)
    assert flag not in segundo.flags_detectados
    assert primero.parametros_aplicados != segundo.parametros_aplicados


def test_n_y_muestreo_se_recargan_en_mismo_adaptador_y_sesion(db_session,administrador,configurados):
    repo,writer=configurados
    globales=SqlAlchemyConfiguracionGlobalRepository(db_session)
    uc=h.calidad_use_case(db_session,repo,globales)
    assert h.evaluar(uc).clasificacion_calidad.value!='INDETERMINADA'
    writer.execute({'rf62_n':8},administrador)
    db_session.execute(text('UPDATE modulo9.configuraciones_globales SET frecuencia_muestreo=9 WHERE es_activo=true'))
    db_session.commit()
    evaluacion=h.evaluar(uc)
    assert evaluacion.clasificacion_calidad.value=='INDETERMINADA'
    assert evaluacion.parametros_aplicados['N']==8 and evaluacion.parametros_aplicados['frecuencia_muestreo_min']==9


def test_confianza_db_cambia_resolucion_real_del_use_case(db_session,administrador,configurados):
    repo,writer=configurados
    uc=h.alerta_use_case(db_session,repo)
    writer.execute({RF57_CONFIANZA:.80},administrador)
    primero=uc.execute(h.evento_alerta())
    writer.execute({RF57_CONFIANZA:.90},administrador)
    segundo=uc.execute(h.evento_alerta())
    assert (primero.tipo_alerta,primero.severidad)==('ESTRES_TERMICO','CRITICO')
    assert (segundo.tipo_alerta,segundo.severidad)==('SINDROME_RESPIRATORIO','MODERADO')


def test_ventana_db_cambia_aceptacion_rf72_sin_recrear_use_case(db_session,administrador,configurados):
    repo,writer=configurados
    uc=h.retro_use_case(db_session,repo)
    assert uc.execute(h.retro_dto(),4).id_retroalimentacion
    writer.execute({RF72_VENTANA:7},administrador)
    with pytest.raises(BusinessRuleError) as error: uc.execute(h.retro_dto(),4)
    assert error.value.code=='FUERA_DE_VENTANA_TEMPORAL'
    assert '7 días' in error.value.message


@pytest.mark.parametrize('sentencia,codigo',[
    ("DELETE FROM modulo4.parametros_mlops WHERE nombre_parametro='rf62_k'",'PARAMETRO_CONFIGURACION_AUSENTE'),
    ("UPDATE modulo4.parametros_mlops SET valor_actual='true' WHERE nombre_parametro='rf62_k'",'PARAMETRO_CONFIGURACION_INVALIDO'),
    ("UPDATE modulo4.parametros_mlops SET valor_actual='1.5' WHERE nombre_parametro='rf62_n'",'PARAMETRO_CONFIGURACION_INVALIDO'),
    ("UPDATE modulo4.parametros_mlops SET rango_maximo=1 WHERE nombre_parametro='rf62_k'",'PARAMETRO_CONFIGURACION_INVALIDO'),
])
def test_configuracion_ausente_o_invalida_no_cae_a_constantes(db_session,configurados,sentencia,codigo):
    repo,_=configurados
    db_session.execute(text(sentencia));db_session.commit()
    adapter=ParametrosCalidadMLOpsAdapter(repo,SqlAlchemyConfiguracionGlobalRepository(db_session))
    with pytest.raises(ServiceUnavailableError) as error: adapter.obtener_parametros(7)
    assert error.value.code==codigo and error.value.status_code==503


def test_actualizacion_invalida_no_modifica_otro_parametro_del_lote(db_session,administrador,configurados):
    repo,writer=configurados
    antes=repo.obtener(['rf62_k',RF72_VENTANA])
    with pytest.raises(ValidationError): writer.execute({'rf62_k':4,RF72_VENTANA:500},administrador)
    assert repo.obtener(['rf62_k',RF72_VENTANA])==antes


def test_actualizacion_conserva_valor_por_defecto_y_atribuye_responsable(db_session,administrador,configurados):
    repo,writer=configurados
    antes=db_session.execute(text('SELECT valor_por_defecto FROM modulo4.parametros_mlops WHERE nombre_parametro=:n'),{'n':RF72_VENTANA}).scalar_one()
    writer.execute({RF72_VENTANA:14},administrador)
    fila=db_session.execute(text('SELECT valor_actual,valor_por_defecto,id_usuario_modificador,fecha_modificacion FROM modulo4.parametros_mlops WHERE nombre_parametro=:n'),{'n':RF72_VENTANA}).one()
    assert fila[0]==14 and fila[1]==antes and fila[2]==administrador and fila[3] is not None


def test_limites_persistidos_se_conservan_al_actualizar(db_session,administrador,configurados):
    repo,writer=configurados
    db_session.execute(text("UPDATE modulo4.parametros_mlops SET rango_maximo=4 WHERE nombre_parametro='rf62_k'"));db_session.commit()
    with pytest.raises(ValidationError): writer.execute({'rf62_k':5},administrador)
    assert repo.obtener(['rf62_k'])['rf62_k'].valor==3


def test_error_de_conexion_se_traduce_sin_filtrar_detalles():
    from sqlalchemy.exc import OperationalError
    from unittest.mock import Mock
    db=Mock()
    db.execute.side_effect=OperationalError('SELECT interno',{},Exception('detalle-interno'))
    with pytest.raises(ServiceUnavailableError) as error: SqlAlchemyParametrosMLOpsRepository(db).obtener([RF72_VENTANA])
    assert error.value.status_code==503 and 'detalle-interno' not in error.value.message


def test_cli_validacion_por_defecto_no_persiste(integration_engine,tmp_path):
    archivo=tmp_path/'parametros.json';archivo.write_text(json.dumps({RF72_VENTANA:14}),encoding='utf8')
    with integration_engine.connect() as c:
        uid=c.execute(text("SELECT u.id_usuario FROM modulo1.usuarios u JOIN modulo1.roles r ON r.id_rol=u.id_rol WHERE lower(r.nombre_rol)='administrador' ORDER BY u.id_usuario LIMIT 1")).scalar_one()
        antes=c.execute(text('SELECT valor_actual FROM modulo4.parametros_mlops WHERE nombre_parametro=:n'),{'n':RF72_VENTANA}).first()
    env=dict(os.environ,DEV14_DATABASE_URL=integration_engine.url.render_as_string(hide_password=False),PYTHONIOENCODING='utf-8')
    resultado=subprocess.run([sys.executable,'scripts/configurar_parametros_dev14.py','--archivo',str(archivo),'--id-usuario',str(uid)],env=env,capture_output=True,text=True,timeout=30)
    assert resultado.returncode==0,resultado.stderr
    assert 'No se realizaron escrituras' in resultado.stdout
    with integration_engine.connect() as c:
        assert c.execute(text('SELECT valor_actual FROM modulo4.parametros_mlops WHERE nombre_parametro=:n'),{'n':RF72_VENTANA}).first()==antes


def test_otro_commit_se_observa_en_misma_sesion_y_consumidor(integration_engine):
    # Se usa una fila propia y se revierte el dato administrativo confirmado al
    # terminar. La BD es exclusivamente de pruebas, nunca DEV compartida.
    from sqlalchemy.dialects.postgresql import insert
    from src.prediction.infrastructure.models.parametro_mlops_model import ParametroMLOpsModel
    tabla=ParametroMLOpsModel.__table__
    with integration_engine.begin() as c:
        original=c.execute(tabla.select().where(tabla.c.nombre_parametro==RF57_CONFIANZA)).mappings().first()
        if original is None:
            c.execute(insert(tabla).values(nombre_parametro=RF57_CONFIANZA,valor_actual=.80,valor_por_defecto=.80,rango_minimo=.70,rango_maximo=.95))
        else:
            c.execute(tabla.update().where(tabla.c.nombre_parametro==RF57_CONFIANZA).values(valor_actual=.80))
    try:
        with Session(integration_engine) as db:
            uc=h.alerta_use_case(db,SqlAlchemyParametrosMLOpsRepository(db))
            assert uc._clasificar(h.evento_alerta())[0]=='ESTRES_TERMICO'
            with integration_engine.begin() as externo:
                externo.execute(tabla.update().where(tabla.c.nombre_parametro==RF57_CONFIANZA).values(valor_actual=.90))
            assert uc._clasificar(h.evento_alerta())[0]=='SINDROME_RESPIRATORIO'
    finally:
        with integration_engine.begin() as c:
            if original is None:
                c.execute(tabla.delete().where(tabla.c.nombre_parametro==RF57_CONFIANZA))
            else:
                c.execute(tabla.update().where(tabla.c.nombre_parametro==RF57_CONFIANZA).values(valor_actual=original['valor_actual']))


def test_rf62_persistencia_completa_dinamica_con_dev02(db_session,administrador,configurados):
    from src.telemetry.domain.repositories.telemetria_repository import TelemetriaRepository
    if hasattr(TelemetriaRepository,'actualizar_flags_aptitud'):
        pytest.skip('Requiere integrar DEV-02; no se duplica su solución de inmutabilidad.')
    from src.telemetry.application.use_cases.calidad.evaluar_calidad_telemetria_use_case import EvaluarCalidadTelemetriaUseCase
    from src.telemetry.infrastructure.repositories.telemetria_repository import SqlAlchemyTelemetriaRepository
    from src.telemetry.infrastructure.repositories.telemetria_calidad_repository import SqlAlchemyTelemetriaCalidadRepository
    repo,writer=configurados
    tag=uuid.uuid4().hex[:12];nombre='Dinamica '+''.join(chr(97+int(c,16)) for c in tag)
    area=db_session.execute(text('''WITH finca AS (INSERT INTO modulo9.fincas(nombre,ubicacion,tamano_h,es_activo,fecha_creacion,fecha_actualizacion)
        VALUES (:n,'{}',10,true,now(),now()) RETURNING id_finca)
        INSERT INTO modulo9.infraestructuras(nombre,id_finca,superficie,es_activo,tipo)
        SELECT :n,id_finca,100,true,'Estanque' FROM finca RETURNING id_infraestructura'''),{'n':nombre}).scalar_one()
    device=db_session.execute(text("INSERT INTO modulo9.dispositivos_iot(serial,descripcion,es_activo,fecha_creacion,id_infraestructura,id_tipo_dispositivo) VALUES (:s,'DEV-14',true,now(),:a,3) RETURNING id_dispositivo_iot"),{'s':tag,'a':area}).scalar_one()
    sensor=db_session.execute(text("INSERT INTO modulo9.sensores(id_dispositivo_iot,es_activo,nombre) VALUES (:d,true,'Sensor dinamico') RETURNING id_sensores"),{'d':device}).scalar_one()
    ids=[];inicio=datetime.now(timezone.utc)-timedelta(minutes=30)
    for i in range(21):
        ids.append(db_session.execute(text('''INSERT INTO modulo3.telemetrias(id_sensor,id_variable,id_dispositivo_iot,
            valor_crudo,valor_ajustado,timestamp_captura,timestamp_procesamiento,origen,estado_calidad,calibrado,
            categoria_variable,unidad_medida,valor_agregado,tipo_dato,metadatos)
            VALUES (:s,9,:d,:v,:v,:ts,now(),'TIEMPO_REAL','LECTURA_VALIDA',true,'AMBIENTAL','°C',false,'CRUDO','{}') RETURNING id_telemetria'''),
            {'s':sensor,'d':device,'v':Decimal(20)+Decimal(i%5)/10,'ts':inicio+timedelta(minutes=i)}).scalar_one())
    db_session.commit()
    antes=db_session.execute(text('SELECT jsonb_agg(to_jsonb(t) ORDER BY id_telemetria) FROM modulo3.telemetrias t WHERE id_sensor=:s'),{'s':sensor}).scalar_one()
    calidad=SqlAlchemyTelemetriaCalidadRepository(db_session)
    uc=EvaluarCalidadTelemetriaUseCase(db_session,SqlAlchemyTelemetriaRepository(db_session),calidad,
        ParametrosCalidadMLOpsAdapter(repo,SqlAlchemyConfiguracionGlobalRepository(db_session)))
    primero=uc.execute(ids[-1],sensor,9,Decimal(20),Decimal(20),inicio+timedelta(minutes=20),'LECTURA_VALIDA',None)
    assert primero.apto_para_ia
    writer.execute({'rf62_n':30},administrador)
    segundo=uc.execute(ids[-1],sensor,9,Decimal(20),Decimal(20),inicio+timedelta(minutes=20),'LECTURA_VALIDA',None)
    assert segundo.clasificacion_calidad.value=='INDETERMINADA' and not segundo.apto_para_ia
    assert calidad.obtener_por_lectura(ids[-1]).id_evaluacion==segundo.id_evaluacion
    assert db_session.execute(text('SELECT jsonb_agg(to_jsonb(t) ORDER BY id_telemetria) FROM modulo3.telemetrias t WHERE id_sensor=:s'),{'s':sensor}).scalar_one()==antes

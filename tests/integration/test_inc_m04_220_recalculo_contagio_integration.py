# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-30 | Leandro | INC-M04-220-G032 RF-68: validar recálculo, caché, configuración, auditoría, alertas y rollback con PostgreSQL y HTTP reales. |
"""G032 con JWT y rol real sgpmp_app; sin desactivar restricciones ni RLS."""
from __future__ import annotations

import importlib
import pkgutil
import uuid
from datetime import datetime, timedelta
from decimal import Decimal as D

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def montar(integration_app):
    for paquete in ('src.configuration.infrastructure.models', 'src.biological_assets.infrastructure.models',
                    'src.telemetry.infrastructure.models'):
        modelos = importlib.import_module(paquete)
        for item in pkgutil.iter_modules(modelos.__path__, paquete + '.'):
            importlib.import_module(item.name)
    from src.prediction.infrastructure.routers.motor_ia_router import router as motor
    from src.prediction.infrastructure.routers.riesgo_contagio_router import router as contagio
    for router, path in ((motor, "/prediccion/motor-ia"), (contagio, "/prediccion/riesgo-contagio")):
        if not any(getattr(r, "path", None)==path and "POST" in getattr(r, "methods", set())
                   for r in integration_app.routes):
            integration_app.include_router(router)
            integration_app.openapi_schema=None


def lote(db, usuario):
    tag = ''.join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:12])
    db.execute(text("INSERT INTO modulo2.estados_activos_biologicos(id_estado_activo_biologico,nombre) VALUES(1,'ACTIVO') ON CONFLICT DO NOTHING"))
    especie = db.execute(text("""INSERT INTO modulo9.especies(nombre,es_activo,fecha_creacion,grupo_manejo,densidad_maxima_por_especie)
        VALUES(:n,true,now(),'AVES',100) RETURNING id_especie"""), {'n': 'Aves Recalculo '+tag}).scalar_one()
    finca = db.execute(text("""INSERT INTO modulo9.fincas(nombre,ubicacion,tamano_h,fecha_actualizacion,fecha_creacion,es_activo)
        VALUES(:n,'{}',10,now(),now(),true) RETURNING id_finca"""), {'n': 'Finca Recalculo '+tag}).scalar_one()
    area = db.execute(text("""INSERT INTO modulo9.infraestructuras(nombre,id_finca,superficie,es_activo,tipo)
        VALUES(:n,:f,100,true,'Corral') RETURNING id_infraestructura"""), {'n': 'Corral Recalculo '+tag, 'f': finca}).scalar_one()
    db.execute(text('INSERT INTO modulo9.infraestructuras_especies(id_infraestructura,id_especie) VALUES(:a,:e)'), {'a': area, 'e': especie})
    db.execute(text('INSERT INTO modulo9.usuarios_fincas(id_usuario,id_finca) VALUES(:u,:f)'), {'u': usuario, 'f': finca})
    db.execute(text("SELECT set_config('app.usuario_id',:u,true)"), {'u': str(usuario)})
    activo = db.execute(text("""INSERT INTO modulo2.activos_biologicos(id_especie,id_infraestructura,tipo,
        fecha_inicio_ciclo,id_estado,descripcion,origen_financiero,costo_adquisicion,atributos_dinamicos,
        id_usuario,fecha_creacion,soporte_documental,detalles_procedencia)
        VALUES(:e,:a,'POBLACIONAL',current_date,1,'Fixture INC-M04-220','compra',100,'{}',:u,now(),'doc','')
        RETURNING id_activo_biologico"""), {'e': especie, 'a': area, 'u': usuario}).scalar_one()
    db.execute(text("""INSERT INTO modulo2.detalles_activos_biologicos_poblacionales
        (id_activo_biologico,cantidad_inicial,peso_promedio_inicial,densidad) VALUES(:l,20,0.1,0.2)"""), {'l': activo})
    return activo


@pytest.fixture
def escenario(db_session, crear_usuario_db, crear_auth_headers, monkeypatch):
    from src.prediction.application.use_cases.riesgo_contagio import estimar_riesgo_contagio_use_case as modulo_uc
    db_session.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    admin = crear_usuario_db(id_rol=1)
    vet = crear_usuario_db(id_rol=3)
    ajeno = crear_usuario_db(id_rol=3)
    productor = crear_usuario_db(id_rol=2)
    propio = lote(db_session, vet['id_usuario'])
    instante = db_session.execute(text('SELECT transaction_timestamp()')).scalar_one()
    reloj = [instante]
    class Reloj(datetime):
        @classmethod
        def now(cls, tz=None):
            return reloj[0]
    monkeypatch.setattr(modulo_uc, 'datetime', Reloj)
    return dict(lote=propio, instante=instante, reloj=reloj, vet_id=vet['id_usuario'],
                admin=crear_auth_headers(admin), vet=crear_auth_headers(vet),
                ajeno=crear_auth_headers(ajeno), productor=crear_auth_headers(productor))


def configurar(client, e):
    r = client.post('/prediccion/motor-ia', headers=e['admin'], json=dict(
        tipo_modelo='MODELO_RIESGO_CONTAGIO', ventana_temporal_min=10, modo_ejecucion='SERVIDOR',
        umbral_riesgo_alto='0.70', umbral_alerta_critica='0.75', w_factor_sanitario='0.5',
        w_factor_ambiental='0.3', w_factor_densidad='0.2', temp_min_config='20', temp_max_config='40',
        hr_min_config='40', hr_max_config='100', densidad_maxima_config='10'))
    assert r.status_code == 201, r.text


def entrada(e, enfermos=4):
    ahora=e['instante'].isoformat()
    return dict(id_lote=e['lote'], total_activos_lote=20,
                salidas_rf66=[dict(id_activo_biologico=n+1,probabilidad_riesgo_alto='.9' if n<enfermos else '.1',
                                  fecha_inferencia=ahora) for n in range(20)],
                variables_ambientales=dict(temperatura='37.5',humedad_relativa='92.5',fecha_captura=ahora),
                densidad_poblacional='8',porcentaje_sensores_activos=100)


def ejecutar(client, e, cuerpo=None, actor='vet'):
    return client.post('/prediccion/riesgo-contagio', headers=e[actor], json=cuerpo or entrada(e))


def resultados(db, e):
    return db.execute(text('SELECT count(*) FROM modulo4.resultados_riesgo_contagio WHERE id_activo_biologico=:l'),
                      {'l':e['lote']}).scalar_one()


def eventos(db, e):
    return db.execute(text("SELECT tipo_evento,codigo_error,resultado_operacion,payload_evento FROM modulo4.eventos_auditoria_m04 WHERE entidad_referencia='lote' AND id_referencia=:l ORDER BY fecha_evento,id_evento"),
                      {'l':str(e['lote'])}).mappings().all()




def preparar(client,e):
    configurar(client,e)
    r=ejecutar(client,e)
    assert r.status_code==201,r.text
    e['reloj'][0]+=timedelta(seconds=2)
    return r.json()


def test_caso_qa_recalcula_tras_dos_segundos_y_conserva_dos_versiones(client,db_session,escenario):
    e=escenario
    primero=preparar(client,e)
    r=ejecutar(client,e,entrada(e,9))
    assert r.status_code==201,r.text
    nuevo=r.json()
    assert D(primero['probabilidad_contagio'])==D('.5225')
    assert D(nuevo['probabilidad_contagio'])==D('.6475') and D(nuevo['factor_sanitario'])==D('.45')
    assert nuevo['id_resultado_contagio']!=primero['id_resultado_contagio'] and nuevo['desde_cache'] is False
    assert resultados(db_session,e)==2
    filas=db_session.execute(text('SELECT probabilidad_contagio,factor_sanitario_fs FROM modulo4.resultados_riesgo_contagio WHERE id_activo_biologico=:l ORDER BY fecha_calculo,id_resultado_contagio'),{'l':e['lote']}).all()
    assert filas==[(D('.5225'),D('.2')),(D('.6475'),D('.45'))]
    ev=eventos(db_session,e)
    assert len(ev)==2 and all(x['tipo_evento']=='RIESGO_CONTAGIO_CALCULADO' for x in ev)
    assert {D(x['payload_evento']['probabilidad_contagio']) for x in ev}=={D('.5225'),D('.6475')}
    cache=ejecutar(client,e,entrada(e,9))
    assert cache.status_code==200 and cache.json()['id_resultado_contagio']==nuevo['id_resultado_contagio']
    assert resultados(db_session,e)==2 and len(eventos(db_session,e))==2


@pytest.mark.parametrize('cambio,esperado',[('ambiente','.4663'),('densidad','.4425'),('score_poblacional','.6475')])
def test_cambios_de_otros_factores_no_responden_429(client,db_session,escenario,cambio,esperado):
    e=escenario
    preparar(client,e)
    cuerpo=entrada(e)
    if cambio=='ambiente':cuerpo['variables_ambientales']['temperatura']='30'
    elif cambio=='densidad':cuerpo['densidad_poblacional']='4'
    else:cuerpo['score_anomalia']='.45'
    r=ejecutar(client,e,cuerpo)
    assert r.status_code==201,r.text
    assert D(r.json()['probabilidad_contagio'])==D(esperado) and resultados(db_session,e)==2


def test_cambio_rf65_version_2_recalcula_sin_esperar(client,db_session,escenario):
    e=escenario
    primero=preparar(client,e)
    r=client.post('/prediccion/motor-ia',headers=e['admin'],json=dict(
        tipo_modelo='MODELO_RIESGO_CONTAGIO',config_version=primero['config_version'],
        ventana_temporal_min=10,modo_ejecucion='SERVIDOR',umbral_riesgo_alto='.70',umbral_alerta_critica='.75',
        w_factor_sanitario='.4',w_factor_ambiental='.4',w_factor_densidad='.2',
        temp_min_config='20',temp_max_config='40',hr_min_config='40',hr_max_config='100',densidad_maxima_config='10'))
    assert r.status_code==200,r.text
    nuevo=ejecutar(client,e)
    assert nuevo.status_code==201,nuevo.text
    assert nuevo.json()['config_version']==primero['config_version']+1
    assert D(nuevo.json()['probabilidad_contagio'])==D('.5900') and resultados(db_session,e)==2


@pytest.mark.parametrize('segundos,estado',[(0,200),(4.999,200),(5,201)])
def test_frontera_cache_y_sin_duplicados(client,db_session,escenario,segundos,estado):
    e=escenario
    primero=preparar(client,e)
    e['reloj'][0]=e['instante']+timedelta(seconds=segundos)
    r=ejecutar(client,e)
    assert r.status_code==estado,r.text
    assert resultados(db_session,e)==(1 if estado==200 else 2)
    assert len(eventos(db_session,e))==(1 if estado==200 else 2)


def test_datos_invalidos_conservan_422_y_auditoria_sin_resultado_extra(client,db_session,escenario):
    e=escenario
    preparar(client,e)
    cuerpo=entrada(e,9)
    cuerpo['porcentaje_sensores_activos']=40
    r=ejecutar(client,e,cuerpo)
    assert r.status_code==422 and r.json()['error_code']=='ERROR_DATOS_INSUFICIENTES',r.text
    assert resultados(db_session,e)==1
    assert {x['tipo_evento'] for x in eventos(db_session,e)}=={'RIESGO_CONTAGIO_CALCULADO','ERROR_DATOS_INSUFICIENTES'}


@pytest.mark.parametrize('fase',['resultado','auditoria'])
def test_fallo_post_flush_revierte_solo_el_nuevo_calculo_y_permite_reintento(client,db_session,escenario,monkeypatch,fase):
    from src.prediction.infrastructure.repositories.resultado_riesgo_contagio_repository import SqlAlchemyResultadoRiesgoContagioRepository
    from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import SqlAlchemyEventoAuditoriaM04Repository
    from src.shared.errors import ServiceUnavailableError
    e=escenario
    primero=preparar(client,e)
    clase=SqlAlchemyResultadoRiesgoContagioRepository if fase=='resultado' else SqlAlchemyEventoAuditoriaM04Repository
    metodo='guardar' if fase=='resultado' else 'registrar'
    original=getattr(clase,metodo)
    def fallar(self,*args,**kw):
        r=original(self,*args,**kw)
        raise ServiceUnavailableError(code='SERVICIO_NO_DISPONIBLE',message='Falla controlada de prueba.')
    monkeypatch.setattr(clase,metodo,fallar)
    r=ejecutar(client,e,entrada(e,9))
    assert r.status_code==503,r.text
    assert resultados(db_session,e)==1 and len(eventos(db_session,e))==1
    previo=db_session.execute(text('SELECT probabilidad_contagio FROM modulo4.resultados_riesgo_contagio WHERE id_resultado_contagio=:id'),{'id':primero['id_resultado_contagio']}).scalar_one()
    assert previo==D('.5225')
    monkeypatch.setattr(clase,metodo,original)
    reintento=ejecutar(client,e,entrada(e,9))
    assert reintento.status_code==201 and resultados(db_session,e)==2,reintento.text


@pytest.mark.parametrize('actor,estado',[('ajeno',404),('productor',403)])
def test_cambio_no_elude_rbac_ni_finca(client,db_session,escenario,actor,estado):
    e=escenario
    preparar(client,e)
    r=ejecutar(client,e,entrada(e,9),actor=actor)
    assert r.status_code==estado,r.text
    assert resultados(db_session,e)==1 and len(eventos(db_session,e))==1


def test_sin_jwt_es_401(client,escenario):
    assert client.post('/prediccion/riesgo-contagio',json=entrada(escenario,9)).status_code==401


def test_recambio_se_persiste_con_rol_real_de_api(client,db_session,escenario,monkeypatch):
    from src.prediction.infrastructure.repositories.resultado_riesgo_contagio_repository import SqlAlchemyResultadoRiesgoContagioRepository
    e=escenario
    preparar(client,e)
    original=SqlAlchemyResultadoRiesgoContagioRepository.guardar
    observados=[]
    def observar(self,resultado):
        observados.extend(self.db.execute(text('SELECT current_user,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')).all())
        return original(self,resultado)
    monkeypatch.setattr(SqlAlchemyResultadoRiesgoContagioRepository,'guardar',observar)
    r=ejecutar(client,e,entrada(e,9))
    assert r.status_code==201,r.text
    assert observados==[('sgpmp_app',False,False)]


def test_openapi_documenta_201_cambiante_y_200_cache_sin_429_obsoleto(client):
    respuestas=client.app.openapi()['paths']['/prediccion/riesgo-contagio']['post']['responses']
    assert '201' in respuestas and '200' in respuestas and '429' not in respuestas


def test_cambio_a_alto_emite_alerta_real_y_cache_no_la_duplica(client,db_session,escenario):
    e=escenario
    preparar(client,e)
    r=ejecutar(client,e,entrada(e,16))
    assert r.status_code==201,r.text
    nueva=r.json()
    assert nueva['alerta_id'] is not None and nueva['nivel_riesgo_contagio']==2
    fila=db_session.execute(text('SELECT tipo_alerta,frecuencia_evento FROM modulo3.alertas WHERE id_alerta=:id'),{'id':nueva['alerta_id']}).one()
    assert fila[0]=='RIESGO_CONTAGIO' and fila[1]==1
    cache=ejecutar(client,e,entrada(e,16))
    assert cache.status_code==200 and cache.json()['alerta_id']==nueva['alerta_id']
    assert db_session.execute(text('SELECT count(*) FROM modulo3.alertas WHERE id_activo_biologico=:l'),{'l':e['lote']}).scalar_one()==1
    assert db_session.execute(text('SELECT frecuencia_evento FROM modulo3.alertas WHERE id_alerta=:id'),{'id':nueva['alerta_id']}).scalar_one()==1
    e['reloj'][0]+=timedelta(seconds=1)
    otro=ejecutar(client,e,entrada(e,17))
    assert otro.status_code==201,otro.text
    assert otro.json()['alerta_id']==nueva['alerta_id']
    assert resultados(db_session,e)==3
    assert db_session.execute(text('SELECT count(*) FROM modulo3.alertas WHERE id_activo_biologico=:l'),{'l':e['lote']}).scalar_one()==1
    assert db_session.execute(text('SELECT frecuencia_evento FROM modulo3.alertas WHERE id_alerta=:id'),{'id':nueva['alerta_id']}).scalar_one()==2


def test_emision_usa_servicio_y_restaura_identidad_del_solicitante(client,db_session,escenario,monkeypatch):
    from src.telemetry.infrastructure.repositories.alerta_repository import SqlAlchemyAlertaRepository
    from src.prediction.infrastructure.repositories.resultado_riesgo_contagio_repository import SqlAlchemyResultadoRiesgoContagioRepository
    e=escenario
    preparar(client,e)
    guardar=SqlAlchemyAlertaRepository.guardar
    asociar=SqlAlchemyResultadoRiesgoContagioRepository.asociar_alerta
    observados=[]
    def ver_emision(self,alerta):
        rol=self.db.execute(text('SELECT current_user,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')).one()
        assert tuple(rol)==('sgpmp_app',False,False)
        assert self.db.execute(text('SELECT modulo1.fn_es_usuario_servicio()')).scalar_one() is True
        observados.append('servicio')
        return guardar(self,alerta)
    def ver_retorno(self,id_resultado,id_alerta):
        assert self.db.execute(text('SELECT modulo1.fn_es_usuario_servicio()')).scalar_one() is False
        assert self.db.execute(text("SELECT current_setting('app.usuario_id')")).scalar_one()==str(e['vet_id'])
        observados.append('solicitante')
        return asociar(self,id_resultado,id_alerta)
    monkeypatch.setattr(SqlAlchemyAlertaRepository,'guardar',ver_emision)
    monkeypatch.setattr(SqlAlchemyResultadoRiesgoContagioRepository,'asociar_alerta',ver_retorno)
    r=ejecutar(client,e,entrada(e,16))
    assert r.status_code==201,r.text
    assert observados==['servicio','solicitante']


def test_fallo_tras_alerta_revierte_calculo_alerta_y_ambas_auditorias(client,db_session,escenario,monkeypatch):
    from src.prediction.application.use_cases.riesgo_contagio.estimar_riesgo_contagio_use_case import EstimarRiesgoContagioUseCase
    from src.shared.errors import ServiceUnavailableError
    e=escenario
    primero=preparar(client,e)
    cantidad_rf63=db_session.execute(text('SELECT count(*) FROM modulo3.bitacora_auditoria_iot')).scalar_one()
    original=EstimarRiesgoContagioUseCase._auditar
    def fallar(self,tipo_evento,*args,**kw):
        original(self,tipo_evento,*args,**kw)
        if tipo_evento=='ALERTA_CONTAGIO_GENERADA':
            raise ServiceUnavailableError(code='SERVICIO_NO_DISPONIBLE',message='Falla controlada tras alerta.')
    monkeypatch.setattr(EstimarRiesgoContagioUseCase,'_auditar',fallar)
    r=ejecutar(client,e,entrada(e,16))
    assert r.status_code==503,r.text
    assert resultados(db_session,e)==1 and len(eventos(db_session,e))==1
    assert db_session.execute(text('SELECT count(*) FROM modulo3.alertas WHERE id_activo_biologico=:l'),{'l':e['lote']}).scalar_one()==0
    assert db_session.execute(text('SELECT count(*) FROM modulo3.bitacora_auditoria_iot')).scalar_one()==cantidad_rf63
    assert db_session.execute(text('SELECT probabilidad_contagio FROM modulo4.resultados_riesgo_contagio WHERE id_resultado_contagio=:id'),{'id':primero['id_resultado_contagio']}).scalar_one()==D('.5225')

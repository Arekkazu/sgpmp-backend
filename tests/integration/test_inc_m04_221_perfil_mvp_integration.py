# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-30 | Leandro | INC-M04-221-G032 RF-68: probar configuración, historial, cálculo MVP, seguridad, alertas y rollback con PostgreSQL real. |
# | 2026-10-31 | Arekkazu | INC-M04-221/222 RF-68: salidas RF-66 con el id del lote (#857) |
"""Contrato RF-65/RF-68 con perfil explícito, sin alterar RLS ni triggers."""
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
        VALUES(:n,true,now(),'AVES',100) RETURNING id_especie"""), {'n': 'Aves Perfil MVP '+tag}).scalar_one()
    finca = db.execute(text("""INSERT INTO modulo9.fincas(nombre,ubicacion,tamano_h,fecha_actualizacion,fecha_creacion,es_activo)
        VALUES(:n,'{}',10,now(),now(),true) RETURNING id_finca"""), {'n': 'Finca Perfil MVP '+tag}).scalar_one()
    area = db.execute(text("""INSERT INTO modulo9.infraestructuras(nombre,id_finca,superficie,es_activo,tipo)
        VALUES(:n,:f,100,true,'Corral') RETURNING id_infraestructura"""), {'n': 'Corral Perfil MVP '+tag, 'f': finca}).scalar_one()
    db.execute(text('INSERT INTO modulo9.infraestructuras_especies(id_infraestructura,id_especie) VALUES(:a,:e)'), {'a': area, 'e': especie})
    db.execute(text('INSERT INTO modulo9.usuarios_fincas(id_usuario,id_finca) VALUES(:u,:f)'), {'u': usuario, 'f': finca})
    db.execute(text("SELECT set_config('app.usuario_id',:u,true)"), {'u': str(usuario)})
    activo = db.execute(text("""INSERT INTO modulo2.activos_biologicos(id_especie,id_infraestructura,tipo,
        fecha_inicio_ciclo,id_estado,descripcion,origen_financiero,costo_adquisicion,atributos_dinamicos,
        id_usuario,fecha_creacion,soporte_documental,detalles_procedencia)
        VALUES(:e,:a,'POBLACIONAL',current_date,1,'Fixture INC-M04-221','compra',100,'{}',:u,now(),'doc','')
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


def configurar(client,e,perfil='MVP',version=None,actor='admin',**cambios):
    cuerpo=dict(tipo_modelo='MODELO_RIESGO_CONTAGIO',ventana_temporal_min=10,modo_ejecucion='SERVIDOR',
        umbral_riesgo_alto='.70',umbral_alerta_critica='.75',w_factor_sanitario='.4',
        w_factor_ambiental='.4',w_factor_densidad='.2',temp_min_config='20',temp_max_config='40',
        hr_min_config='40',hr_max_config='100',densidad_maxima_config='10')
    if perfil is not None:cuerpo['perfil_calculo_contagio']=perfil
    if version is not None:cuerpo['config_version']=version
    cuerpo.update(cambios)
    return client.post('/prediccion/motor-ia',headers=e[actor],json=cuerpo)


def entrada(e, enfermos=4):
    ahora=e['instante'].isoformat()
    return dict(id_lote=e['lote'], total_activos_lote=20,
                salidas_rf66=[dict(id_activo_biologico=e['lote'],probabilidad_riesgo_alto='.9' if n<enfermos else '.1',
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






def activar(client,e,perfil='MVP',version=None,**campos):
    r=configurar(client,e,perfil,version,**campos)
    assert r.status_code==(201 if version is None else 200),r.text
    return r.json()


@pytest.mark.parametrize('segundos',[0,2])
def test_mvp_recalcula_entradas_identicas_y_persiste_pesos_perfil_auditoria(client,db_session,escenario,segundos):
    e=escenario
    c=activar(client,e)
    assert c['modo_ejecucion']=='SERVIDOR' and c['perfil_calculo_contagio']=='MVP'
    assert [D(c[k]) for k in ('w_factor_sanitario','w_factor_ambiental','w_factor_densidad')]==[D('.5'),D('.3'),D('.2')]
    r1=ejecutar(client,e)
    e['reloj'][0]+=timedelta(seconds=segundos)
    r2=ejecutar(client,e)
    assert r1.status_code==r2.status_code==201,(r1.text,r2.text)
    a,b=r1.json(),r2.json()
    assert a['id_resultado_contagio']!=b['id_resultado_contagio']
    assert not a['desde_cache'] and not b['desde_cache'] and resultados(db_session,e)==2
    assert D(b['probabilidad_contagio'])==D('.5225') and b['perfil_calculo_contagio']=='MVP'
    assert b['modo_ejecucion']=='NORMAL'
    filas=db_session.execute(text('SELECT variables_ambientales_snap,w_fs_aplicado,w_fa_aplicado,w_fd_aplicado FROM modulo4.resultados_riesgo_contagio WHERE id_activo_biologico=:l'),{'l':e['lote']}).all()
    assert all(f[0]['perfil_calculo_contagio']=='MVP' and f[1:]==(D('.5'),D('.3'),D('.2')) for f in filas)
    ev=eventos(db_session,e)
    assert len(ev)==2 and all(x['payload_evento']['perfil_calculo_contagio']=='MVP' for x in ev)
    assert all(x['payload_evento']['pesos_aplicados']=={'fs':'0.500','fa':'0.300','fd':'0.200'} for x in ev)


def test_omitir_perfil_conserva_estandar_cache_y_pesos_personalizados(client,db_session,escenario):
    e=escenario
    c=activar(client,e,None)
    assert c['perfil_calculo_contagio']=='ESTANDAR'
    primero=ejecutar(client,e)
    e['reloj'][0]+=timedelta(seconds=2)
    segundo=ejecutar(client,e)
    assert primero.status_code==201 and segundo.status_code==200,segundo.text
    assert segundo.json()['desde_cache'] and D(segundo.json()['probabilidad_contagio'])==D('.5900')
    assert resultados(db_session,e)==1 and len(eventos(db_session,e))==1


def test_transiciones_versionadas_conservan_historial_y_no_mezclan_cache(client,db_session,escenario):
    e=escenario
    c1=activar(client,e,'ESTANDAR')
    r1=ejecutar(client,e)
    e['reloj'][0]+=timedelta(seconds=1)
    c2=activar(client,e,'MVP',c1['config_version'])
    r2=ejecutar(client,e)
    c3=activar(client,e,'ESTANDAR',c2['config_version'])
    r3=ejecutar(client,e)
    assert [r.status_code for r in (r1,r2,r3)]==[201,201,201],r3.text
    assert [D(r.json()['probabilidad_contagio']) for r in (r1,r2,r3)]==[D('.5900'),D('.5225'),D('.5900')]
    assert resultados(db_session,e)==3
    historia=client.get('/prediccion/motor-ia/MODELO_RIESGO_CONTAGIO/historial',headers=e['admin'])
    assert historia.status_code==200,historia.text
    versiones=historia.json()['versiones']
    assert [v['configuracion']['perfil_calculo_contagio'] for v in versiones]==['ESTANDAR','MVP','ESTANDAR']
    assert [v['config_version'] for v in versiones]==[3,2,1]
    configurado=client.get('/prediccion/motor-ia/MODELO_RIESGO_CONTAGIO',headers=e['admin'])
    assert configurado.status_code==200 and configurado.json()['perfil_calculo_contagio']=='ESTANDAR'
    audit=db_session.execute(text("SELECT payload_evento FROM modulo4.eventos_auditoria_m04 WHERE entidad_referencia='configuracion_motor_ia' AND id_referencia=:c AND tipo_evento='CONFIGURACION_MOTOR_CAMBIADA'"),{'c':str(c1['id_configuracion_motor'])}).scalars().all()
    assert len(audit)==3
    assert {x['valores_nuevos']['perfil_calculo_contagio'] for x in audit}=={'ESTANDAR','MVP'}


def test_edicion_con_version_obsoleta_no_cambia_perfil(client,db_session,escenario):
    e=escenario
    c=activar(client,e)
    activar(client,e,'ESTANDAR',c['config_version'])
    r=configurar(client,e,'MVP',c['config_version'])
    assert r.status_code==412,r.text
    assert db_session.execute(text("SELECT perfil_calculo_contagio FROM modulo4.configuraciones_motor_ia WHERE tipo_modelo='MODELO_RIESGO_CONTAGIO'")).scalar_one()=='ESTANDAR'


@pytest.mark.parametrize('cambios,codigo',[
    ({'modo_ejecucion':'MVP'},'MODO_EJECUCION_INVALIDO'),
    ({'perfil_calculo_contagio':'OTRO'},'PERFIL_CALCULO_CONTAGIO_INVALIDO'),
    ({'tipo_modelo':'MODELO_AVES'},'PERFIL_MVP_NO_APLICA'),
    ({'w_factor_sanitario':'-.1','w_factor_ambiental':'.9'},'PESOS_CONTAGIO_INVALIDOS'),
])
def test_rechazos_configuracion_no_crean_filas(client,db_session,escenario,cambios,codigo):
    e=escenario
    perfil=cambios.get('perfil_calculo_contagio','MVP')
    cambios={k:v for k,v in cambios.items() if k!='perfil_calculo_contagio'}
    r=configurar(client,e,perfil,**cambios)
    assert r.status_code==422 and r.json()['error_code']==codigo,r.text
    assert db_session.execute(text('SELECT count(*) FROM modulo4.configuraciones_motor_ia')).scalar_one()==0


@pytest.mark.parametrize('defecto',['sensores','inferencias_obsoletas'])
def test_mvp_conserva_controles_de_datos_y_auditoria(client,db_session,escenario,defecto):
    e=escenario
    activar(client,e)
    cuerpo=entrada(e)
    if defecto=='sensores':cuerpo['porcentaje_sensores_activos']=40
    else:
        for s in cuerpo['salidas_rf66']:s['fecha_inferencia']=(e['instante']-timedelta(minutes=31)).isoformat()
    r=ejecutar(client,e,cuerpo)
    assert r.status_code==422 and r.json()['error_code']=='ERROR_DATOS_INSUFICIENTES',r.text
    assert resultados(db_session,e)==0
    ev,=eventos(db_session,e)
    assert ev['payload_evento']['perfil_calculo_contagio']=='MVP'


@pytest.mark.parametrize('actor,estado',[('ajeno',404),('productor',403)])
def test_mvp_no_elude_rbac_ni_finca(client,db_session,escenario,actor,estado):
    e=escenario
    activar(client,e)
    r=ejecutar(client,e,actor=actor)
    assert r.status_code==estado,r.text
    assert resultados(db_session,e)==0


def test_mvp_exige_jwt_y_no_habilita_configuracion_al_productor(client,db_session,escenario):
    e=escenario
    assert configurar(client,e,actor='productor').status_code==403
    activar(client,e)
    assert client.post('/prediccion/riesgo-contagio',json=entrada(e)).status_code==401


def test_alerta_mvp_real_se_consolida_y_restaura_al_solicitante(client,db_session,escenario,monkeypatch):
    from src.prediction.infrastructure.repositories.resultado_riesgo_contagio_repository import SqlAlchemyResultadoRiesgoContagioRepository
    e=escenario
    activar(client,e)
    original=SqlAlchemyResultadoRiesgoContagioRepository.asociar_alerta
    vistos=[]
    def observar(self,*args):
        assert self.db.execute(text('SELECT modulo1.fn_es_usuario_servicio()')).scalar_one() is False
        assert self.db.execute(text('SELECT current_user')).scalar_one()=='sgpmp_app'
        vistos.append(True)
        return original(self,*args)
    monkeypatch.setattr(SqlAlchemyResultadoRiesgoContagioRepository,'asociar_alerta',observar)
    primero=ejecutar(client,e,entrada(e,16))
    e['reloj'][0]+=timedelta(seconds=2)
    segundo=ejecutar(client,e,entrada(e,16))
    assert primero.status_code==segundo.status_code==201,(primero.text,segundo.text)
    a,b=primero.json(),segundo.json()
    assert a['alerta_id']==b['alerta_id'] and a['id_resultado_contagio']!=b['id_resultado_contagio']
    assert db_session.execute(text('SELECT count(*) FROM modulo3.alertas WHERE id_activo_biologico=:l'),{'l':e['lote']}).scalar_one()==1
    assert db_session.execute(text('SELECT frecuencia_evento FROM modulo3.alertas WHERE id_alerta=:a'),{'a':a['alerta_id']}).scalar_one()==2
    assert vistos==[True,True]


@pytest.mark.parametrize('fase',['resultado','auditoria','alerta'])
def test_fallo_post_flush_revierte_nueva_operacion_mvp(client,db_session,escenario,monkeypatch,fase):
    from src.prediction.infrastructure.repositories.resultado_riesgo_contagio_repository import SqlAlchemyResultadoRiesgoContagioRepository
    from src.prediction.application.use_cases.riesgo_contagio.estimar_riesgo_contagio_use_case import EstimarRiesgoContagioUseCase
    from src.shared.errors import ServiceUnavailableError
    e=escenario
    activar(client,e)
    primero=ejecutar(client,e)
    assert primero.status_code==201,primero.text
    e['reloj'][0]+=timedelta(seconds=2)
    if fase=='resultado':
        original=SqlAlchemyResultadoRiesgoContagioRepository.guardar
        def fallar(self,r):
            original(self,r)
            raise ServiceUnavailableError('SERVICIO_NO_DISPONIBLE','Fallo controlado tras resultado.')
        monkeypatch.setattr(SqlAlchemyResultadoRiesgoContagioRepository,'guardar',fallar)
    else:
        original=EstimarRiesgoContagioUseCase._auditar
        def fallar(self,tipo,*args,**kwargs):
            original(self,tipo,*args,**kwargs)
            if tipo==('RIESGO_CONTAGIO_CALCULADO' if fase=='auditoria' else 'ALERTA_CONTAGIO_GENERADA'):
                raise ServiceUnavailableError('SERVICIO_NO_DISPONIBLE','Fallo controlado tras auditoría.')
        monkeypatch.setattr(EstimarRiesgoContagioUseCase,'_auditar',fallar)
    cantidad_rf63=db_session.execute(text('SELECT count(*) FROM modulo3.bitacora_auditoria_iot')).scalar_one()
    r=ejecutar(client,e,entrada(e,16))
    assert r.status_code==503,r.text
    assert resultados(db_session,e)==1 and len(eventos(db_session,e))==1
    assert db_session.execute(text('SELECT count(*) FROM modulo3.alertas WHERE id_activo_biologico=:l'),{'l':e['lote']}).scalar_one()==0
    assert db_session.execute(text('SELECT count(*) FROM modulo3.bitacora_auditoria_iot')).scalar_one()==cantidad_rf63


def test_lectura_legacy_sin_perfil_en_snapshot_se_interpreta_estandar(client,db_session,escenario):
    from src.prediction.infrastructure.repositories.resultado_riesgo_contagio_repository import SqlAlchemyResultadoRiesgoContagioRepository
    from src.prediction.infrastructure.models.resultado_riesgo_contagio_model import ResultadoRiesgoContagioModel
    e=escenario
    activar(client,e,'ESTANDAR')
    r=ejecutar(client,e)
    assert r.status_code==201,r.text
    ident=db_session.execute(text("""INSERT INTO modulo4.resultados_riesgo_contagio(id_activo_biologico,id_configuracion_motor,
        factor_sanitario_fs,w_fs_aplicado,w_fa_aplicado,w_fd_aplicado,probabilidad_contagio,nivel_riesgo_contagio,
        fecha_calculo,variables_ambientales_snap) SELECT id_activo_biologico,id_configuracion_motor,
        factor_sanitario_fs,w_fs_aplicado,w_fa_aplicado,w_fd_aplicado,probabilidad_contagio,nivel_riesgo_contagio,
        fecha_calculo - interval '1 minute',variables_ambientales_snap - 'perfil_calculo_contagio'
        FROM modulo4.resultados_riesgo_contagio WHERE id_resultado_contagio=:id RETURNING id_resultado_contagio"""),
        {'id':r.json()['id_resultado_contagio']}).scalar_one()
    dominio=SqlAlchemyResultadoRiesgoContagioRepository._a_entidad(db_session.get(ResultadoRiesgoContagioModel,ident))
    assert dominio.perfil_calculo_contagio=='ESTANDAR' and 'perfil_calculo_contagio' not in dominio.variables_ambientales


def test_constraints_e_inmutabilidad_del_historial_no_se_relajan(client,db_session,escenario):
    from sqlalchemy.exc import DBAPIError
    e=escenario
    c=activar(client,e)
    activar(client,e,'ESTANDAR',c['config_version'])
    with pytest.raises(DBAPIError) as exc:
        with db_session.begin_nested():
            db_session.execute(text("UPDATE modulo4.configuraciones_motor_ia SET perfil_calculo_contagio='OTRO' WHERE id_configuracion_motor=:id"),{'id':c['id_configuracion_motor']})
    assert exc.value.orig.pgcode=='23514'
    otro=activar(client,e,'ESTANDAR',tipo_modelo='MODELO_ESPECIES_GRANDES')
    with pytest.raises(DBAPIError) as fuera:
        with db_session.begin_nested():
            db_session.execute(text("UPDATE modulo4.configuraciones_motor_ia SET perfil_calculo_contagio='MVP' WHERE id_configuracion_motor=:id"),{'id':otro['id_configuracion_motor']})
    assert fuera.value.orig.pgcode=='23514'
    with pytest.raises(DBAPIError):
        with db_session.begin_nested():
            db_session.execute(text('UPDATE modulo4.configuracion_ia_log SET perfil_calculo_contagio=perfil_calculo_contagio'))
    assert db_session.execute(text('SELECT perfil_calculo_contagio FROM modulo4.configuracion_ia_log WHERE id_configuracion_motor=:id'),{'id':c['id_configuracion_motor']}).scalar_one()=='MVP'


def test_mvp_degradado_repetido_conserva_aviso_e10_auditable(client,db_session,escenario):
    e=escenario
    activar(client,e)
    cuerpo=entrada(e)
    cuerpo['variables_ambientales']=None
    for _ in range(6):
        r=ejecutar(client,e,cuerpo)
        assert r.status_code==201,r.text
        assert r.json()['confianza_baja'] is True and r.json()['desde_cache'] is False
        e['reloj'][0]+=timedelta(seconds=2)
    assert resultados(db_session,e)==6
    avisos=[x for x in eventos(db_session,e) if x['tipo_evento']=='ALERTA_CALIDAD_DATOS']
    assert len(avisos)==1
    assert avisos[0]['resultado_operacion']=='PARCIAL'
    assert avisos[0]['payload_evento']['perfil_calculo_contagio']=='MVP'
    assert avisos[0]['payload_evento']['ejecuciones_degradadas_consecutivas']==6
    assert db_session.execute(text('SELECT count(*) FROM modulo3.alertas WHERE id_activo_biologico=:l'),{'l':e['lote']}).scalar_one()==0

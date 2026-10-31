# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-30 | Leandro | INC-M04-222-G034 RF-68: probar aislamiento de RF-66, cálculo, seguridad, alertas y rollback con PostgreSQL real. |
"""Contrato RF-65/RF-68 con aislamiento por identidad del lote, sin alterar RLS ni triggers."""
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
        VALUES(:n,true,now(),'AVES',100) RETURNING id_especie"""), {'n': 'Aves Aislamiento Sanitario '+tag}).scalar_one()
    finca = db.execute(text("""INSERT INTO modulo9.fincas(nombre,ubicacion,tamano_h,fecha_actualizacion,fecha_creacion,es_activo)
        VALUES(:n,'{}',10,now(),now(),true) RETURNING id_finca"""), {'n': 'Finca Aislamiento Sanitario '+tag}).scalar_one()
    area = db.execute(text("""INSERT INTO modulo9.infraestructuras(nombre,id_finca,superficie,es_activo,tipo)
        VALUES(:n,:f,100,true,'Corral') RETURNING id_infraestructura"""), {'n': 'Corral Aislamiento Sanitario '+tag, 'f': finca}).scalar_one()
    db.execute(text('INSERT INTO modulo9.infraestructuras_especies(id_infraestructura,id_especie) VALUES(:a,:e)'), {'a': area, 'e': especie})
    db.execute(text('INSERT INTO modulo9.usuarios_fincas(id_usuario,id_finca) VALUES(:u,:f)'), {'u': usuario, 'f': finca})
    db.execute(text("SELECT set_config('app.usuario_id',:u,true)"), {'u': str(usuario)})
    activo = db.execute(text("""INSERT INTO modulo2.activos_biologicos(id_especie,id_infraestructura,tipo,
        fecha_inicio_ciclo,id_estado,descripcion,origen_financiero,costo_adquisicion,atributos_dinamicos,
        id_usuario,fecha_creacion,soporte_documental,detalles_procedencia)
        VALUES(:e,:a,'POBLACIONAL',current_date,1,'Fixture INC-M04-222','compra',100,'{}',:u,now(),'doc','')
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
    otros = [lote(db_session, vet['id_usuario']) for _ in range(4)]
    otros.append(lote(db_session, ajeno['id_usuario']))
    instante = db_session.execute(text('SELECT transaction_timestamp()')).scalar_one()
    reloj = [instante]
    class Reloj(datetime):
        @classmethod
        def now(cls, tz=None):
            return reloj[0]
    monkeypatch.setattr(modulo_uc, 'datetime', Reloj)
    return dict(lote=propio, otros=otros, instante=instante, reloj=reloj, vet_id=vet['id_usuario'],
                admin=crear_auth_headers(admin), vet=crear_auth_headers(vet),
                ajeno=crear_auth_headers(ajeno), productor=crear_auth_headers(productor))


def configurar(client,e,version=None,actor='admin',**cambios):
    cuerpo=dict(tipo_modelo='MODELO_RIESGO_CONTAGIO',ventana_temporal_min=10,modo_ejecucion='SERVIDOR',
        umbral_riesgo_alto='.70',umbral_alerta_critica='.75',w_factor_sanitario='.5',
        w_factor_ambiental='.3',w_factor_densidad='.2',temp_min_config='20',temp_max_config='40',
        hr_min_config='40',hr_max_config='100',densidad_maxima_config='10')
    if version is not None:cuerpo['config_version']=version
    cuerpo.update(cambios)
    return client.post('/prediccion/motor-ia',headers=e[actor],json=cuerpo)


def entrada(e, enfermos=3, ajenas=False):
    ahora = e['instante'].isoformat()
    salidas = [dict(id_activo_biologico=e['lote'], probabilidad_riesgo_alto='.9' if n<enfermos else '.1',
                    fecha_inferencia=ahora) for n in range(10)]
    if ajenas:
        salidas += [dict(id_activo_biologico=n, probabilidad_riesgo_alto='.95', fecha_inferencia=ahora)
                    for n in e['otros']]
    return dict(id_lote=e['lote'], total_activos_lote=10, salidas_rf66=salidas,
        variables_ambientales=dict(temperatura='30', humedad_relativa='70', fecha_captura=ahora),
        densidad_poblacional='6', porcentaje_sensores_activos=100)

def ejecutar(client, e, cuerpo=None, actor='vet'):
    return client.post('/prediccion/riesgo-contagio', headers=e[actor], json=cuerpo or entrada(e))


def resultados(db, e):
    return db.execute(text('SELECT count(*) FROM modulo4.resultados_riesgo_contagio WHERE id_activo_biologico=:l'),
                      {'l':e['lote']}).scalar_one()


def eventos(db, e):
    return db.execute(text("SELECT tipo_evento,codigo_error,resultado_operacion,payload_evento FROM modulo4.eventos_auditoria_m04 WHERE entidad_referencia='lote' AND id_referencia=:l ORDER BY fecha_evento,id_evento"),
                      {'l':str(e['lote'])}).mappings().all()






@pytest.fixture(autouse=True)
def activar(client, escenario, montar):
    r = configurar(client, escenario)
    assert r.status_code == 201, r.text


def test_mezcla_con_otras_fincas_conserva_baseline_y_no_alerta(client, db_session, escenario):
    e = escenario
    a = ejecutar(client, e)
    assert a.status_code == 201, a.text
    e['reloj'][0] += timedelta(seconds=6)
    b = ejecutar(client, e, entrada(e, ajenas=True))
    assert b.status_code == 201, b.text
    for respuesta in (a, b):
        r = respuesta.json()
        assert r['n_enfermos_detectados'] == 3
        assert D(r['factor_sanitario']) == D('.3')
        assert D(r['probabilidad_contagio']) == D('.42')
        assert r['nivel_riesgo_contagio'] == 0 and r['alerta_id'] is None
    assert resultados(db_session, e) == 2
    assert len(eventos(db_session, e)) == 2
    assert db_session.execute(text('SELECT count(*) FROM modulo3.alertas WHERE id_activo_biologico=:l'),
                              {'l':e['lote']}).scalar_one() == 0
    filas = db_session.execute(text('SELECT factor_sanitario_fs,n_enfermos_detectados,probabilidad_contagio FROM modulo4.resultados_riesgo_contagio WHERE id_activo_biologico=:l'),{'l':e['lote']}).all()
    assert all(tuple(f)==(D('.3'),3,D('.42')) for f in filas)


@pytest.mark.parametrize('actor,estado',[('ajeno',404),('productor',403)])
def test_acceso_al_lote_no_se_amplia(client, db_session, escenario, actor, estado):
    r = ejecutar(client, escenario, actor=actor)
    assert r.status_code == estado, r.text
    assert resultados(db_session, escenario) == 0


def test_jwt_obligatorio(client, escenario):
    assert client.post('/prediccion/riesgo-contagio',json=entrada(escenario)).status_code == 401

@pytest.mark.parametrize('sin_id', [False, True])
def test_ninguna_salida_propia_responde_422_y_conserva_evidencia(client, db_session, escenario, sin_id):
    e=escenario
    cuerpo=entrada(e,ajenas=True)
    cuerpo['salidas_rf66']=cuerpo['salidas_rf66'][10:]
    if sin_id:
        for s in cuerpo['salidas_rf66']:s.pop('id_activo_biologico')
    r=ejecutar(client,e,cuerpo)
    assert r.status_code==422 and r.json()['error_code']=='ERROR_DATOS_INSUFICIENTES',r.text
    assert resultados(db_session,e)==0
    ev,=eventos(db_session,e)
    assert ev['tipo_evento']=='ERROR_DATOS_INSUFICIENTES' and ev['resultado_operacion']=='FALLIDO'
    assert ev['payload_evento']['aislamiento_rf66']['conservadas']==0


def test_conteo_cliente_no_reincorpora_enfermos_ajenos(client, db_session, escenario):
    e=escenario
    cuerpo=entrada(e,ajenas=True)
    cuerpo['n_enfermos_detectados']=8
    cuerpo['salidas_rf66'].append(dict(probabilidad_riesgo_alto='.99',fecha_inferencia=e['instante'].isoformat()))
    for s in cuerpo['salidas_rf66'][10:]:
        s['fecha_inferencia']=(e['instante']-timedelta(minutes=40)).isoformat()
    r=ejecutar(client,e,cuerpo)
    assert r.status_code==201,r.text
    assert r.json()['n_enfermos_detectados']==3 and D(r.json()['probabilidad_contagio'])==D('.42')
    ev,=eventos(db_session,e)
    assert ev['payload_evento']['aislamiento_rf66']==dict(recibidas=16,conservadas=10,descartadas_otro_lote=5,descartadas_sin_identidad=1)


def test_compartir_infraestructura_no_acredita_ser_el_mismo_lote(client, db_session, escenario):
    e=escenario
    # Otro lote real del mismo usuario, especie y área; no hay vínculo de pertenencia.
    db_session.execute(text("SELECT set_config('app.usuario_id',:u,true)"),{'u':str(e['vet_id'])})
    otro=db_session.execute(text("""INSERT INTO modulo2.activos_biologicos(id_especie,id_infraestructura,tipo,
        fecha_inicio_ciclo,id_estado,descripcion,origen_financiero,costo_adquisicion,atributos_dinamicos,
        id_usuario,fecha_creacion,soporte_documental,detalles_procedencia)
        SELECT id_especie,id_infraestructura,tipo,fecha_inicio_ciclo,id_estado,descripcion,origen_financiero,
        costo_adquisicion,atributos_dinamicos,id_usuario,now(),soporte_documental,detalles_procedencia
        FROM modulo2.activos_biologicos WHERE id_activo_biologico=:l RETURNING id_activo_biologico"""),{'l':e['lote']}).scalar_one()
    cuerpo=entrada(e)
    cuerpo['salidas_rf66'] += [dict(id_activo_biologico=otro,probabilidad_riesgo_alto='.99',fecha_inferencia=e['instante'].isoformat()) for _ in range(5)]
    r=ejecutar(client,e,cuerpo)
    assert r.status_code==201,r.text
    assert r.json()['n_enfermos_detectados']==3 and r.json()['alerta_id'] is None


def test_cache_no_se_contamina_al_agregar_salidas_ajenas(client, db_session, escenario):
    e=escenario
    a=ejecutar(client,e)
    assert a.status_code==201,a.text
    e['reloj'][0]+=timedelta(seconds=2)
    b=ejecutar(client,e,entrada(e,ajenas=True))
    assert b.status_code==200,b.text
    assert a.json()['id_resultado_contagio']==b.json()['id_resultado_contagio']
    assert D(b.json()['factor_sanitario'])==D('.3') and b.json()['desde_cache'] is True
    assert resultados(db_session,e)==1 and len(eventos(db_session,e))==1


def test_riesgo_real_propio_genera_alerta_y_auditoria(client, db_session, escenario, monkeypatch):
    from src.prediction.infrastructure.repositories.resultado_riesgo_contagio_repository import SqlAlchemyResultadoRiesgoContagioRepository
    original=SqlAlchemyResultadoRiesgoContagioRepository.asociar_alerta
    identidades=[]
    def comprobar_identidad(self,*args):
        identidades.append(self.db.execute(text('SELECT current_user,modulo1.fn_es_usuario_servicio()')).one())
        return original(self,*args)
    monkeypatch.setattr(SqlAlchemyResultadoRiesgoContagioRepository,'asociar_alerta',comprobar_identidad)
    e=escenario
    r=ejecutar(client,e,entrada(e,enfermos=8,ajenas=True))
    assert r.status_code==201,r.text
    assert r.json()['n_enfermos_detectados']==8 and r.json()['nivel_riesgo_contagio']==2
    assert r.json()['alerta_id'] is not None
    assert db_session.execute(text('SELECT count(*) FROM modulo3.alertas WHERE id_activo_biologico=:l'),{'l':e['lote']}).scalar_one()==1
    assert [x['tipo_evento'] for x in eventos(db_session,e)]==['RIESGO_CONTAGIO_CALCULADO','ALERTA_CONTAGIO_GENERADA']
    assert identidades==[('sgpmp_app',False)]
    assert db_session.execute(text('SELECT count(*) FROM modulo3.bitacora_auditoria_iot')).scalar_one()>0


@pytest.mark.parametrize('fase',['resultado','auditoria','alerta'])
def test_fallo_revierte_calculo_filtrado_y_alerta(client, db_session, escenario, monkeypatch, fase):
    from src.prediction.infrastructure.repositories.resultado_riesgo_contagio_repository import SqlAlchemyResultadoRiesgoContagioRepository
    from src.prediction.application.use_cases.riesgo_contagio.estimar_riesgo_contagio_use_case import EstimarRiesgoContagioUseCase
    from src.shared.errors import ServiceUnavailableError
    e=escenario
    a=ejecutar(client,e)
    assert a.status_code==201,a.text
    e['reloj'][0]+=timedelta(seconds=6)
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
    antes=db_session.execute(text('SELECT count(*) FROM modulo3.bitacora_auditoria_iot')).scalar_one()
    r=ejecutar(client,e,entrada(e,enfermos=8,ajenas=True))
    assert r.status_code==503,r.text
    assert resultados(db_session,e)==1 and len(eventos(db_session,e))==1
    assert db_session.execute(text('SELECT count(*) FROM modulo3.alertas WHERE id_activo_biologico=:l'),{'l':e['lote']}).scalar_one()==0
    assert db_session.execute(text('SELECT count(*) FROM modulo3.bitacora_auditoria_iot')).scalar_one()==antes


def test_modelo_poblacional_conserva_score_independiente(client, db_session, escenario):
    e=escenario
    cuerpo=entrada(e,ajenas=True)
    cuerpo['salidas_rf66']=cuerpo['salidas_rf66'][10:]
    cuerpo['score_anomalia']='.3'
    r=ejecutar(client,e,cuerpo)
    assert r.status_code==201,r.text
    assert D(r.json()['factor_sanitario'])==D('.3')
    assert r.json()['definicion_fs']=='SCORE_POBLACIONAL'


def test_http_bajo_rol_real_y_consulta_posterior(client, db_session, escenario, monkeypatch):
    from src.prediction.infrastructure.repositories.resultado_riesgo_contagio_repository import SqlAlchemyResultadoRiesgoContagioRepository
    e=escenario
    original=SqlAlchemyResultadoRiesgoContagioRepository.guardar
    vistos=[]
    def observar(self,r):
        vistos.append(self.db.execute(text("SELECT current_user,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user")).one())
        return original(self,r)
    monkeypatch.setattr(SqlAlchemyResultadoRiesgoContagioRepository,'guardar',observar)
    a=ejecutar(client,e,entrada(e,ajenas=True))
    assert a.status_code==201,a.text
    assert vistos==[('sgpmp_app',False,False)]
    b=client.get('/prediccion/riesgo-contagio',headers=e['vet'])
    assert b.status_code==200,b.text
    item,=[x for x in b.json() if x['id_resultado_contagio']==a.json()['id_resultado_contagio']]
    assert D(item['probabilidad_contagio'])==D('.42')

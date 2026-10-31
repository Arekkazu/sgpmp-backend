# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-30 | Leandro | INC-M04-219-G030 RF-68: validar cobertura, caché, auditoría, aislamiento y rollback con HTTP y PostgreSQL reales. |
# | 2026-10-31 | Arekkazu | INC-M04-219/222 RF-68: salidas con el id del lote; la variante duplicada pasa a otro lote |
"""RF-68 G030 con JWT y rol sgpmp_app, sin desactivar triggers ni restricciones."""
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
    integration_app.include_router(motor)
    integration_app.include_router(contagio)


def lote(db, usuario):
    tag = ''.join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:12])
    db.execute(text("INSERT INTO modulo2.estados_activos_biologicos(id_estado_activo_biologico,nombre) VALUES(1,'ACTIVO') ON CONFLICT DO NOTHING"))
    especie = db.execute(text("""INSERT INTO modulo9.especies(nombre,es_activo,fecha_creacion,grupo_manejo,densidad_maxima_por_especie)
        VALUES(:n,true,now(),'AVES',100) RETURNING id_especie"""), {'n': 'Aves Cobertura '+tag}).scalar_one()
    finca = db.execute(text("""INSERT INTO modulo9.fincas(nombre,ubicacion,tamano_h,fecha_actualizacion,fecha_creacion,es_activo)
        VALUES(:n,'{}',10,now(),now(),true) RETURNING id_finca"""), {'n': 'Finca Cobertura '+tag}).scalar_one()
    area = db.execute(text("""INSERT INTO modulo9.infraestructuras(nombre,id_finca,superficie,es_activo,tipo)
        VALUES(:n,:f,100,true,'Corral') RETURNING id_infraestructura"""), {'n': 'Corral Cobertura '+tag, 'f': finca}).scalar_one()
    db.execute(text('INSERT INTO modulo9.infraestructuras_especies(id_infraestructura,id_especie) VALUES(:a,:e)'), {'a': area, 'e': especie})
    db.execute(text('INSERT INTO modulo9.usuarios_fincas(id_usuario,id_finca) VALUES(:u,:f)'), {'u': usuario, 'f': finca})
    db.execute(text("SELECT set_config('app.usuario_id',:u,true)"), {'u': str(usuario)})
    activo = db.execute(text("""INSERT INTO modulo2.activos_biologicos(id_especie,id_infraestructura,tipo,
        fecha_inicio_ciclo,id_estado,descripcion,origen_financiero,costo_adquisicion,atributos_dinamicos,
        id_usuario,fecha_creacion,soporte_documental,detalles_procedencia)
        VALUES(:e,:a,'POBLACIONAL',current_date,1,'Fixture INC-M04-219','compra',100,'{}',:u,now(),'doc','')
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
    class Reloj(datetime):
        @classmethod
        def now(cls, tz=None):
            return instante
    monkeypatch.setattr(modulo_uc, 'datetime', Reloj)
    return dict(lote=propio, instante=instante, vet_id=vet['id_usuario'],
                admin=crear_auth_headers(admin), vet=crear_auth_headers(vet),
                ajeno=crear_auth_headers(ajeno), productor=crear_auth_headers(productor))


def configurar(client, e):
    r = client.post('/prediccion/motor-ia', headers=e['admin'], json=dict(
        tipo_modelo='MODELO_RIESGO_CONTAGIO', ventana_temporal_min=10, modo_ejecucion='SERVIDOR',
        umbral_riesgo_alto='0.70', umbral_alerta_critica='0.75', w_factor_sanitario='0.5',
        w_factor_ambiental='0.3', w_factor_densidad='0.2', temp_min_config='20', temp_max_config='40',
        hr_min_config='40', hr_max_config='100', densidad_maxima_config='15'))
    assert r.status_code == 201, r.text


def entrada(e, cantidad=12):
    ahora = e['instante'].isoformat()
    return dict(id_lote=e['lote'], total_activos_lote=20,
                salidas_rf66=[dict(id_activo_biologico=e['lote'], probabilidad_riesgo_alto='.9' if n<4 else '.1',
                                  fecha_inferencia=ahora) for n in range(cantidad)],
                variables_ambientales=dict(temperatura='30', humedad_relativa='70', fecha_captura=ahora),
                densidad_poblacional='7.5', porcentaje_sensores_activos=100)


def ejecutar(client, e, cuerpo=None, actor='vet'):
    return client.post('/prediccion/riesgo-contagio', headers=e[actor], json=cuerpo or entrada(e))


def resultados(db, e):
    return db.execute(text('SELECT count(*) FROM modulo4.resultados_riesgo_contagio WHERE id_activo_biologico=:l'),
                      {'l':e['lote']}).scalar_one()


def eventos(db, e):
    return db.execute(text("SELECT tipo_evento,codigo_error,resultado_operacion,payload_evento FROM modulo4.eventos_auditoria_m04 WHERE entidad_referencia='lote' AND id_referencia=:l ORDER BY fecha_evento,id_evento"),
                      {'l':str(e['lote'])}).mappings().all()


@pytest.mark.parametrize('cantidad', [0,9,10,11])
def test_baja_cobertura_devuelve_422_audita_y_no_persiste_resultado_ni_alerta(client, db_session, escenario, cantidad):
    e=escenario
    configurar(client,e)
    antes=db_session.execute(text('SELECT count(*) FROM modulo3.alertas')).scalar_one()
    for _ in range(2):
        r=ejecutar(client,e,entrada(e,cantidad))
        assert r.status_code == 422, r.text
        assert r.json()['error_code'] == 'ERROR_DATOS_INSUFICIENTES'
    assert resultados(db_session,e) == 0
    assert db_session.execute(text('SELECT count(*) FROM modulo3.alertas')).scalar_one() == antes
    filas=eventos(db_session,e)
    assert len(filas) == 2 and all(f['tipo_evento']=='ERROR_DATOS_INSUFICIENTES' for f in filas)
    for f in filas:
        assert f['codigo_error']=='ERROR_DATOS_INSUFICIENTES' and f['resultado_operacion']=='FALLIDO'
        assert f['payload_evento']['inferencias_recientes']==cantidad
        assert f['payload_evento']['total_activos_lote']==20
        assert D(f['payload_evento']['cobertura_minima_rf66'])==D('.60')
        assert D(f['payload_evento']['cobertura_rf66'])==D(cantidad)/20


@pytest.mark.parametrize('cantidad', [12,13,20])
def test_desde_60_persiste_formula_y_cache_validos(client, db_session, escenario, cantidad):
    e=escenario
    configurar(client,e)
    cuerpo=entrada(e,cantidad)
    r=ejecutar(client,e,cuerpo)
    assert r.status_code==201,r.text
    fila=r.json()
    assert D(fila['factor_sanitario'])==D('.2') and D(fila['probabilidad_contagio'])==D('.3500')
    assert fila['modo_ejecucion']=='NORMAL' and fila['confianza_baja'] is False
    assert fila['alerta_id'] is None and resultados(db_session,e)==1
    assert [x['tipo_evento'] for x in eventos(db_session,e)]==['RIESGO_CONTAGIO_CALCULADO']
    cache=ejecutar(client,e,cuerpo)
    assert cache.status_code==200 and cache.json()['id_resultado_contagio']==fila['id_resultado_contagio']
    assert resultados(db_session,e)==1 and len(eventos(db_session,e))==1


@pytest.mark.parametrize('variante', ['obsoleta','futura','otro_lote'])
def test_inferencia_no_util_no_completa_la_cobertura(client, db_session, escenario, variante):
    e=escenario
    configurar(client,e)
    cuerpo=entrada(e)
    ultima=cuerpo['salidas_rf66'][-1]
    if variante=='obsoleta':
        ultima['fecha_inferencia']=(e['instante']-timedelta(minutes=31)).isoformat()
    elif variante=='futura':
        ultima['fecha_inferencia']=(e['instante']+timedelta(seconds=1)).isoformat()
    else:
        # #857: las salidas propias traen el id del lote; una de otro lote se descarta.
        ultima['id_activo_biologico']=e['lote']+100000
    r=ejecutar(client,e,cuerpo)
    assert r.status_code==422 and r.json()['error_code']=='ERROR_DATOS_INSUFICIENTES',r.text
    assert resultados(db_session,e)==0
    assert eventos(db_session,e)[0]['payload_evento']['inferencias_recientes']==11


def test_score_poblacional_no_requiere_inferencias_individuales(client, db_session, escenario):
    e=escenario
    configurar(client,e)
    cuerpo=entrada(e,0)
    cuerpo['score_anomalia']='.2'
    r=ejecutar(client,e,cuerpo)
    assert r.status_code==201,r.text
    assert r.json()['definicion_fs']=='SCORE_POBLACIONAL'
    assert D(r.json()['factor_sanitario'])==D('.2') and r.json()['confianza_baja'] is False
    assert resultados(db_session,e)==1


def test_resultado_legacy_en_cache_no_elude_el_minimo(client, db_session, escenario):
    from src.prediction.application.use_cases.riesgo_contagio.estimar_riesgo_contagio_use_case import EstimarRiesgoContagioUseCase
    from src.prediction.infrastructure.dto.estimar_riesgo_contagio_dto import EstimarRiesgoContagioDTO
    from src.prediction.infrastructure.repositories.resultado_riesgo_contagio_repository import SqlAlchemyResultadoRiesgoContagioRepository
    e=escenario
    configurar(client,e)
    valido=ejecutar(client,e).json()
    repo=SqlAlchemyResultadoRiesgoContagioRepository(db_session)
    historico=repo.ultimos_por_lote(e['lote'],1)[0]
    cuerpo=entrada(e,11)
    historico.huella_entradas=EstimarRiesgoContagioUseCase._huella(EstimarRiesgoContagioDTO(**cuerpo),historico.config_version)
    # Simula un resultado previo a #854; no modifica el registro válido existente.
    repo.guardar(historico)
    assert resultados(db_session,e)==2
    r=ejecutar(client,e,cuerpo)
    assert r.status_code==422 and r.json()['error_code']=='ERROR_DATOS_INSUFICIENTES',r.text
    assert resultados(db_session,e)==2
    assert sum(x['tipo_evento']=='ERROR_DATOS_INSUFICIENTES' for x in eventos(db_session,e))==1


@pytest.mark.parametrize('actor,estado', [('ajeno',404),('productor',403)])
def test_autorizacion_precede_validacion_sin_exponer_lote(client, db_session, escenario, actor, estado):
    e=escenario
    configurar(client,e)
    r=ejecutar(client,e,entrada(e,11),actor=actor)
    assert r.status_code==estado,r.text
    assert resultados(db_session,e)==0 and eventos(db_session,e)==[]


def test_sin_jwt_es_401(client, escenario):
    r=client.post('/prediccion/riesgo-contagio',json=entrada(escenario,11))
    assert r.status_code==401


def test_fallo_controlado_post_flush_revierte_auditoria(client, db_session, escenario, monkeypatch):
    from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import SqlAlchemyEventoAuditoriaM04Repository
    from src.shared.errors import ServiceUnavailableError
    original=SqlAlchemyEventoAuditoriaM04Repository.registrar
    e=escenario
    configurar(client,e)
    def fallar(self, **kw):
        r=original(self, **kw)
        if kw['tipo_evento']=='ERROR_DATOS_INSUFICIENTES':
            raise ServiceUnavailableError(code='SERVICIO_NO_DISPONIBLE',message='Falla controlada de prueba.')
        return r
    monkeypatch.setattr(SqlAlchemyEventoAuditoriaM04Repository,'registrar',fallar)
    r=ejecutar(client,e,entrada(e,11))
    assert r.status_code==503,r.text
    assert resultados(db_session,e)==0 and eventos(db_session,e)==[]


def test_rechazo_se_audita_con_el_rol_real_de_api(client, db_session, escenario, monkeypatch):
    from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import SqlAlchemyEventoAuditoriaM04Repository
    original=SqlAlchemyEventoAuditoriaM04Repository.registrar
    observados=[]
    def observar(self, **kw):
        if kw['tipo_evento']=='ERROR_DATOS_INSUFICIENTES':
            observados.extend(self._db.execute(text('SELECT current_user,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')).all())
        return original(self, **kw)
    e=escenario
    configurar(client,e)
    monkeypatch.setattr(SqlAlchemyEventoAuditoriaM04Repository,'registrar',observar)
    r=ejecutar(client,e,entrada(e,11))
    assert r.status_code==422,r.text
    assert observados==[('sgpmp_app',False,False)]
    assert resultados(db_session,e)==0
    assert eventos(db_session,e)[0]['tipo_evento']=='ERROR_DATOS_INSUFICIENTES'

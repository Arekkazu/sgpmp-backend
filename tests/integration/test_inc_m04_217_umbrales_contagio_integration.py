# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-30 | Leandro | INC-M04-217-G026 RF-68: verificar umbrales y flujo en entorno aislado. |
# | 2026-10-31 | Arekkazu | INC-M04-217/222 RF-68: salidas RF-66 con el id del lote (#857) |
"""RF-65 → RF-68 → RF-57/RF-73 con PostgreSQL, JWT, RBAC y RLS reales."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

import uuid
import importlib
import pkgutil

pytestmark = pytest.mark.integration
D = Decimal
TIPO = 'MODELO_RIESGO_CONTAGIO'


@pytest.fixture(autouse=True)
def montar_routers(integration_app):
    # Igual que el arranque completo: registrar las FK de los módulos relacionados.
    for paquete in ("src.configuration.infrastructure.models",
                    "src.biological_assets.infrastructure.models",
                    "src.telemetry.infrastructure.models"):
        modelos = importlib.import_module(paquete)
        for item in pkgutil.iter_modules(modelos.__path__, paquete + "."):
            importlib.import_module(item.name)
    from src.prediction.infrastructure.routers.motor_ia_router import router as motor
    from src.prediction.infrastructure.routers.riesgo_contagio_router import router as contagio
    integration_app.include_router(motor)
    integration_app.include_router(contagio)


@pytest.fixture
def escenario(db_session, crear_usuario_db, crear_auth_headers):
    admin = crear_usuario_db(id_rol=1)
    vet = crear_usuario_db(id_rol=3)
    ajeno = crear_usuario_db(id_rol=3)
    productor = crear_usuario_db(id_rol=2)
    tag = ''.join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:12])
    db_session.execute(text("INSERT INTO modulo2.estados_activos_biologicos(id_estado_activo_biologico,nombre) VALUES(1,'ACTIVO') ON CONFLICT DO NOTHING"))
    especie = db_session.execute(text("INSERT INTO modulo9.especies(nombre,es_activo,fecha_creacion,grupo_manejo,densidad_maxima_por_especie) VALUES(:n,true,now(),'AVES',100) RETURNING id_especie"), {'n': 'Aves Contagio '+tag}).scalar_one()
    finca = db_session.execute(text("INSERT INTO modulo9.fincas(nombre,ubicacion,tamano_h,fecha_actualizacion,fecha_creacion,es_activo) VALUES(:n,'{}',10,now(),now(),true) RETURNING id_finca"), {'n': 'Finca Contagio '+tag}).scalar_one()
    area = db_session.execute(text("INSERT INTO modulo9.infraestructuras(nombre,id_finca,superficie,es_activo,tipo) VALUES(:n,:f,100,true,'Corral') RETURNING id_infraestructura"), {'n': 'Galpon Contagio '+tag, 'f': finca}).scalar_one()
    db_session.execute(text('INSERT INTO modulo9.infraestructuras_especies(id_infraestructura,id_especie) VALUES(:a,:e)'), {'a': area, 'e': especie})
    db_session.execute(text('INSERT INTO modulo9.usuarios_fincas(id_usuario,id_finca) VALUES(:u,:f)'), {'u': vet['id_usuario'], 'f': finca})
    db_session.execute(text("SELECT set_config('app.usuario_id',:u,true)"), {'u': str(vet['id_usuario'])})
    lote = db_session.execute(text("""INSERT INTO modulo2.activos_biologicos(id_especie,identificador,id_infraestructura,tipo,fecha_inicio_ciclo,id_estado,descripcion,origen_financiero,costo_adquisicion,atributos_dinamicos,id_usuario,fecha_creacion,soporte_documental,detalles_procedencia)
        VALUES(:e,NULL,:a,'POBLACIONAL',current_date,1,'Fixture INC-M04-217','compra',100,'{}',:u,now(),'doc','') RETURNING id_activo_biologico"""), {'e': especie, 'a': area, 'u': vet['id_usuario']}).scalar_one()
    db_session.execute(text('INSERT INTO modulo9.usuarios_fincas(id_usuario,id_finca) VALUES (:u,:f)'),
                       {'u': admin['id_usuario'], 'f': finca})
    return dict(lote=lote, area=area, admin=crear_auth_headers(admin),
                vet=crear_auth_headers(vet), ajeno=crear_auth_headers(ajeno),
                productor=crear_auth_headers(productor))


def configurar(client, headers, alto='0.90', critica='0.95', version=None):
    cuerpo = dict(tipo_modelo=TIPO, ventana_temporal_min=10, modo_ejecucion='SERVIDOR',
                  umbral_riesgo_alto=alto, umbral_alerta_critica=critica,
                  w_factor_sanitario='0.5', w_factor_ambiental='0.3', w_factor_densidad='0.2',
                  temp_min_config='20', temp_max_config='36', hr_min_config='40', hr_max_config='90',
                  densidad_maxima_config='15')
    if version is not None:
        cuerpo['config_version'] = version
    r = client.post('/prediccion/motor-ia', headers=headers, json=cuerpo)
    assert r.status_code == (201 if version is None else 200), r.text
    return r.json()


def entrada(lote, probabilidad='0.8', qa=False):
    ahora = datetime.now(timezone.utc).isoformat()
    cuerpo = dict(id_lote=lote, porcentaje_sensores_activos=100, densidad_poblacional='15',
                  variables_ambientales=dict(temperatura='36', humedad_relativa='90', fecha_captura=ahora))
    if qa:
        cuerpo.update(total_activos_lote=20, salidas_rf66=[
            dict(id_activo_biologico=lote, probabilidad_riesgo_alto=p, fecha_inferencia=ahora) for p in ['0.9'] * 12 + ['0.1'] * 8])
    else:
        cuerpo['score_anomalia'] = str((D(probabilidad) - D('0.5')) / D('0.5'))
    return cuerpo


def ejecutar(client, e, cuerpo=None, actor='vet'):
    return client.post('/prediccion/riesgo-contagio', headers=e[actor], json=cuerpo or entrada(e['lote']))


def test_configuracion_actualizada_corrige_qa_y_conserva_snapshot_auditable(client, db_session, escenario):
    e = escenario
    creada = configurar(client, e['admin'], '0.50', '0.75')
    assert creada['config_version'] == 1
    editada = configurar(client, e['admin'], version=1)
    assert editada['config_version'] == 2
    cuerpo = entrada(e['lote'], qa=True)
    r = ejecutar(client, e, cuerpo)
    assert r.status_code == 201, r.text
    salida = r.json()
    assert D(salida['probabilidad_contagio']) == D('0.8')
    assert salida['nivel_riesgo_contagio'] == 1 and salida['alerta_id'] is None
    assert salida['config_version'] == 2
    fila = db_session.execute(text('SELECT * FROM modulo4.resultados_riesgo_contagio WHERE id_resultado_contagio=:id'),
                              {'id': salida['id_resultado_contagio']}).mappings().one()
    snap = fila['variables_ambientales_snap']
    assert fila['nivel_riesgo_contagio'] == 1 and snap['config_version'] == 2
    assert {k: D(v) for k, v in snap['umbrales_aplicados'].items()} == {
        'umbral_riesgo_alto': D('0.90'), 'umbral_alerta_critica': D('0.95')}
    assert db_session.execute(text('SELECT count(*) FROM modulo3.alertas WHERE id_activo_biologico=:l'),
                              {'l': e['lote']}).scalar_one() == 0
    auditoria = db_session.execute(text("SELECT payload_evento FROM modulo4.eventos_auditoria_m04 WHERE tipo_evento='RIESGO_CONTAGIO_CALCULADO' AND id_referencia=:id"),
                                   {'id': str(e['lote'])}).scalar_one()
    assert auditoria['umbrales_aplicados'] == snap['umbrales_aplicados']
    cache = ejecutar(client, e, cuerpo)
    assert cache.status_code == 200 and cache.json()['id_resultado_contagio'] == salida['id_resultado_contagio']
    assert db_session.execute(text('SELECT count(*) FROM modulo4.resultados_riesgo_contagio WHERE id_activo_biologico=:l'),
                              {'l': e['lote']}).scalar_one() == 1


@pytest.mark.parametrize('p,nivel,alerta', [
    ('0.8999', 1, False), ('0.90', 2, False), ('0.9001', 2, False),
    ('0.9499', 2, False), ('0.95', 2, True), ('0.9501', 2, True),
])
def test_fronteras_de_clasificacion_y_alerta_en_bd_real(client, db_session, escenario, p, nivel, alerta):
    e = escenario
    configurar(client, e['admin'])
    r = ejecutar(client, e, entrada(e['lote'], p))
    assert r.status_code == 201, r.text
    salida = r.json()
    assert D(salida['probabilidad_contagio']) == D(p)
    assert salida['nivel_riesgo_contagio'] == nivel
    assert (salida['alerta_id'] is not None) is alerta
    alertas = db_session.execute(text('SELECT * FROM modulo3.alertas WHERE id_activo_biologico=:l'),
                                 {'l': e['lote']}).mappings().all()
    assert len(alertas) == int(alerta)
    if alerta:
        assert alertas[0]['tipo_alerta'] == 'RIESGO_CONTAGIO' and alertas[0]['severidad'] == 'CRITICO'
        assert alertas[0]['reglas_activas'][0]['config_version'] == salida['config_version']
        assert alertas[0]['id_alerta'] == salida['alerta_id']


def test_jwt_rbac_y_finca_siguen_protegiendo_el_calculo(client, db_session, escenario):
    e = escenario
    configurar(client, e['admin'])
    cuerpo = entrada(e['lote'])
    assert client.post('/prediccion/riesgo-contagio', json=cuerpo).status_code == 401
    assert ejecutar(client, e, cuerpo, 'productor').status_code == 403
    assert ejecutar(client, e, cuerpo, 'ajeno').status_code == 404
    assert db_session.execute(text('SELECT count(*) FROM modulo4.resultados_riesgo_contagio WHERE id_activo_biologico=:l'),
                              {'l': e['lote']}).scalar_one() == 0


def test_un_fallo_despues_de_generar_alerta_revierte_resultado_alerta_y_auditoria(client, db_session, escenario, monkeypatch):
    from src.prediction.application.use_cases.riesgo_contagio.estimar_riesgo_contagio_use_case import EstimarRiesgoContagioUseCase
    e = escenario
    configurar(client, e['admin'])
    auditar = EstimarRiesgoContagioUseCase._auditar

    def fallar(self, tipo_evento, *args, **kw):
        auditar(self, tipo_evento, *args, **kw)
        if tipo_evento == 'ALERTA_CONTAGIO_GENERADA':
            raise RuntimeError('fallo controlado tras persistir alerta')

    with monkeypatch.context() as m:
        m.setattr(EstimarRiesgoContagioUseCase, '_auditar', fallar)
        with pytest.raises(RuntimeError, match='fallo controlado'):
            ejecutar(client, e, entrada(e['lote'], '0.96'))
    for tabla in ('modulo4.resultados_riesgo_contagio', 'modulo3.alertas'):
        assert db_session.execute(text('SELECT count(*) FROM '+tabla+' WHERE id_activo_biologico=:l'),
                                  {'l': e['lote']}).scalar_one() == 0
    assert db_session.execute(text("SELECT count(*) FROM modulo4.eventos_auditoria_m04 WHERE id_referencia=:id AND tipo_evento IN ('RIESGO_CONTAGIO_CALCULADO','ALERTA_CONTAGIO_GENERADA')"),
                              {'id': str(e['lote'])}).scalar_one() == 0


def test_http_usa_rol_normal_y_politicas_forzadas(client, db_session, escenario, monkeypatch):
    from src.prediction.infrastructure.repositories.resultado_riesgo_contagio_repository import SqlAlchemyResultadoRiesgoContagioRepository
    e = escenario
    configurar(client, e['admin'])
    guardar = SqlAlchemyResultadoRiesgoContagioRepository.guardar
    asociar = SqlAlchemyResultadoRiesgoContagioRepository.asociar_alerta
    observados = []

    def comprobar(self, resultado):
        rol = self.db.execute(text('SELECT current_user,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')).one()
        assert tuple(rol) == ('sgpmp_app', False, False)
        rls = self.db.execute(text("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='modulo4.resultados_riesgo_contagio'::regclass")).one()
        assert tuple(rls) == (True, True)
        observados.append(True)
        return guardar(self, resultado)

    def comprobar_retorno(self, id_resultado, id_alerta):
        assert self.db.execute(text('SELECT current_user')).scalar_one() == 'sgpmp_app'
        assert self.db.execute(text('SELECT modulo1.fn_es_usuario_servicio()')).scalar_one() is False
        observados.append('identidad_restaurada')
        return asociar(self, id_resultado, id_alerta)

    monkeypatch.setattr(SqlAlchemyResultadoRiesgoContagioRepository, 'guardar', comprobar)
    monkeypatch.setattr(SqlAlchemyResultadoRiesgoContagioRepository, 'asociar_alerta', comprobar_retorno)
    r = ejecutar(client, e, entrada(e['lote'], '0.96'))
    assert r.status_code == 201, r.text
    assert observados == [True, 'identidad_restaurada']


def test_nueva_version_aplica_a_nuevo_ciclo_sin_reclasificar_historial(client, db_session, escenario, monkeypatch):
    from src.prediction.application.use_cases.riesgo_contagio import estimar_riesgo_contagio_use_case as modulo_uc
    e = escenario
    configurar(client, e['admin'], '0.70', '0.75')
    cuerpo = entrada(e['lote'], qa=True)
    anterior = ejecutar(client, e, cuerpo)
    assert anterior.status_code == 201, anterior.text
    antes = anterior.json()
    assert antes['nivel_riesgo_contagio'] == 2 and antes['alerta_id'] is not None
    configurar(client, e['admin'], version=1)
    instante = datetime.now(timezone.utc) + timedelta(seconds=6)

    class Reloj(datetime):
        @classmethod
        def now(cls, tz=None):
            return instante

    monkeypatch.setattr(modulo_uc, 'datetime', Reloj)
    nuevo = ejecutar(client, e, cuerpo)
    assert nuevo.status_code == 201, nuevo.text
    despues = nuevo.json()
    assert despues['config_version'] == 2 and despues['nivel_riesgo_contagio'] == 1
    assert despues['alerta_id'] is None and not despues['desde_cache']
    assert despues['id_resultado_contagio'] != antes['id_resultado_contagio']
    filas = db_session.execute(text('SELECT nivel_riesgo_contagio,variables_ambientales_snap FROM modulo4.resultados_riesgo_contagio WHERE id_activo_biologico=:l ORDER BY id_resultado_contagio'), {'l': e['lote']}).all()
    assert len(filas) == 2
    assert filas[0][0] == 2 and filas[0][1]['config_version'] == 1
    assert D(filas[0][1]['umbrales_aplicados']['umbral_riesgo_alto']) == D('0.70')
    assert filas[1][0] == 1 and filas[1][1]['config_version'] == 2
    assert D(filas[1][1]['umbrales_aplicados']['umbral_riesgo_alto']) == D('0.90')

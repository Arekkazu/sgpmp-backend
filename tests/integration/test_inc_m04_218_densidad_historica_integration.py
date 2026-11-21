# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-30 | Leandro | INC-M04-218-G029 RF-68: validar E2, auditoría, ventana y aislamiento con PostgreSQL y HTTP reales. |
# | 2026-10-31 | Arekkazu | INC-M04-218/222 RF-68: salidas RF-66 con el id del lote (#857) |
"""Base exclusiva: histórico sintético identificado y prueba separada del trigger real."""
from __future__ import annotations

import importlib
import json
import pkgutil
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import text

from src.prediction.infrastructure.adapters.ocupacion_lote_m02_adapter import OcupacionLoteM02Adapter
from src.shared.database import declarar_identidad

pytestmark = pytest.mark.integration
D = Decimal


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
        VALUES(:n,true,now(),'AVES',100) RETURNING id_especie"""), {'n': 'Aves Ocupacion '+tag}).scalar_one()
    finca = db.execute(text("""INSERT INTO modulo9.fincas(nombre,ubicacion,tamano_h,fecha_actualizacion,fecha_creacion,es_activo)
        VALUES(:n,'{}',10,now(),now(),true) RETURNING id_finca"""), {'n': 'Finca Ocupacion '+tag}).scalar_one()
    area = db.execute(text("""INSERT INTO modulo9.infraestructuras(nombre,id_finca,superficie,es_activo,tipo)
        VALUES(:n,:f,100,true,'Corral') RETURNING id_infraestructura"""), {'n': 'Corral Ocupacion '+tag, 'f': finca}).scalar_one()
    db.execute(text('INSERT INTO modulo9.infraestructuras_especies(id_infraestructura,id_especie) VALUES(:a,:e)'), {'a': area, 'e': especie})
    db.execute(text('INSERT INTO modulo9.usuarios_fincas(id_usuario,id_finca) VALUES(:u,:f)'), {'u': usuario, 'f': finca})
    db.execute(text("SELECT set_config('app.usuario_id',:u,true)"), {'u': str(usuario)})
    activo = db.execute(text("""INSERT INTO modulo2.activos_biologicos(id_especie,id_infraestructura,tipo,
        fecha_inicio_ciclo,id_estado,descripcion,origen_financiero,costo_adquisicion,atributos_dinamicos,
        id_usuario,fecha_creacion,soporte_documental,detalles_procedencia)
        VALUES(:e,:a,'POBLACIONAL',current_date,1,'Fixture INC-M04-218','compra',100,'{}',:u,now(),'doc','')
        RETURNING id_activo_biologico"""), {'e': especie, 'a': area, 'u': usuario}).scalar_one()
    db.execute(text("""INSERT INTO modulo2.detalles_activos_biologicos_poblacionales
        (id_activo_biologico,cantidad_inicial,peso_promedio_inicial,densidad) VALUES(:l,950,0.1,9.5)"""), {'l': activo})
    return activo


@pytest.fixture
def escenario(db_session, crear_usuario_db, crear_auth_headers, monkeypatch):
    from src.prediction.application.use_cases.riesgo_contagio import estimar_riesgo_contagio_use_case as modulo_uc
    # La API fija UTC al conectar; la conexión de la fixture debe hacer lo mismo.
    db_session.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    admin = crear_usuario_db(id_rol=1)
    vet = crear_usuario_db(id_rol=3)
    ajeno = crear_usuario_db(id_rol=3)
    productor = crear_usuario_db(id_rol=2)
    propio = lote(db_session, vet['id_usuario'])
    externo = lote(db_session, ajeno['id_usuario'])
    instante = db_session.execute(text('SELECT transaction_timestamp()')).scalar_one()

    class Reloj(datetime):
        @classmethod
        def now(cls, tz=None):
            return instante

    monkeypatch.setattr(modulo_uc, 'datetime', Reloj)
    return dict(lote=propio, externo=externo, instante=instante, vet_id=vet['id_usuario'],
                admin=crear_auth_headers(admin), vet=crear_auth_headers(vet),
                ajeno=crear_auth_headers(ajeno), productor=crear_auth_headers(productor))


def estado(db, e, dias, densidad, *, id_lote=None, operacion='UPDATE'):
    """Fixture histórica explícita. No modifica logs existentes ni desactiva triggers."""
    datos = json.dumps({'id_activo_biologico': id_lote or e['lote'], 'densidad': densidad})
    return db.execute(text("""INSERT INTO auditoria.logs_dml(fecha_evento,usuario_bd,esquema_afectado,
        tabla_afectada,tipo_operacion,datos_nuevos,datos_anteriores,aplicacion)
        VALUES(:fecha AT TIME ZONE 'UTC','fixture-inc853','modulo2','detalles_activos_biologicos_poblacionales',
            :op,CASE WHEN :op='DELETE' THEN NULL ELSE CAST(:dato AS jsonb) END,
            CAST(:dato AS jsonb),'fixture-inc853') RETURNING id_log"""),
        {'fecha': e['instante']-timedelta(days=dias), 'op': operacion, 'dato': datos}).scalar_one()


def configurar(client, e):
    r = client.post('/prediccion/motor-ia', headers=e['admin'], json=dict(
        tipo_modelo='MODELO_RIESGO_CONTAGIO', ventana_temporal_min=10, modo_ejecucion='SERVIDOR',
        umbral_riesgo_alto='0.70', umbral_alerta_critica='0.75', w_factor_sanitario='0.5',
        w_factor_ambiental='0.3', w_factor_densidad='0.2', temp_min_config='20', temp_max_config='40',
        hr_min_config='40', hr_max_config='100', densidad_maxima_config='15'))
    assert r.status_code == 201, r.text


def entrada(e, densidad='-5'):
    ahora = e['instante'].isoformat()
    return dict(id_lote=e['lote'], total_activos_lote=10,
                salidas_rf66=[dict(id_activo_biologico=e['lote'], probabilidad_riesgo_alto=p, fecha_inferencia=ahora)
                              for p in ['0.9']*2 + ['0.1']*8],
                variables_ambientales=dict(temperatura='30',humedad_relativa='70',fecha_captura=ahora),
                densidad_poblacional=densidad, porcentaje_sensores_activos=100)


def ejecutar(client, e, cuerpo=None, actor='vet'):
    return client.post('/prediccion/riesgo-contagio', headers=e[actor], json=cuerpo or entrada(e))


def test_caso_qa_promedio_9_5_fd_0_6333_y_auditoria_sin_cambiar_la_lectura(client, db_session, escenario):
    e = escenario
    ids = [estado(db_session,e,30,'8'), estado(db_session,e,15,'11')]
    configurar(client,e)
    cuerpo = entrada(e)
    r = ejecutar(client,e,cuerpo)
    assert r.status_code == 201, r.text
    salida = r.json()
    assert D(salida['factor_densidad']) == D('0.6333')
    assert D(salida['probabilidad_contagio']) == D('0.3767')
    assert salida['densidad_asumida'] is False and salida['confianza_baja'] is False
    assert salida['alerta_id'] is None
    snap = db_session.execute(text('SELECT variables_ambientales_snap FROM modulo4.resultados_riesgo_contagio WHERE id_resultado_contagio=:id'), {'id': salida['id_resultado_contagio']}).scalar_one()
    contexto = snap['contexto_densidad']
    assert contexto['fuente'] == 'HISTORICO_OCUPACION_M02'
    assert contexto['densidad_solicitada'] == '-5' and D(contexto['densidad_aplicada']) == D('9.5')
    assert contexto['historico']['primer_id_registro'] == ids[0]
    assert contexto['historico']['ultimo_id_registro'] == ids[1]
    assert D(contexto['historico']['segundos_cubiertos']) == D(30*86400)
    auditoria = db_session.execute(text("SELECT payload_evento FROM modulo4.eventos_auditoria_m04 WHERE tipo_evento='RIESGO_CONTAGIO_CALCULADO' AND id_referencia=:l"), {'l': str(e['lote'])}).scalar_one()
    assert auditoria['contexto_densidad'] == contexto
    assert db_session.execute(text('SELECT densidad FROM modulo2.detalles_activos_biologicos_poblacionales WHERE id_activo_biologico=:l'), {'l': e['lote']}).scalar_one() == D('9.5')
    cache = ejecutar(client,e,cuerpo)
    assert cache.status_code == 200 and cache.json()['id_resultado_contagio'] == salida['id_resultado_contagio']


def test_previo_limite_futuro_y_otro_lote_no_contaminan_promedio(client, db_session, escenario):
    e = escenario
    estado(db_session,e,90,'999')
    estado(db_session,e,31,'8')
    estado(db_session,e,15,'11')
    estado(db_session,e,-1,'999')
    estado(db_session,e,30,'999',id_lote=e['externo'])
    configurar(client,e)
    r = ejecutar(client,e)
    assert r.status_code == 201, r.text
    assert D(r.json()['factor_densidad']) == D('0.6333')


@pytest.mark.parametrize('invalida', [None, '-8', 'NaN', 'Infinity', 'dato-malformado'])
def test_periodos_invalidos_no_prolongan_el_valor_previo(client, db_session, escenario, invalida):
    e = escenario
    estado(db_session,e,30,'8')
    estado(db_session,e,20,invalida)
    estado(db_session,e,10,'11')
    configurar(client,e)
    r = ejecutar(client,e)
    assert r.status_code == 201, r.text
    assert D(r.json()['factor_densidad']) == D('0.6333')


def test_sin_historia_util_es_preventivo_degradado_y_no_alerta(client, db_session, escenario):
    e = escenario
    configurar(client,e)
    cuerpo = entrada(e)
    cuerpo['salidas_rf66'] = []
    cuerpo['score_anomalia'] = '1'
    cuerpo['variables_ambientales'].update(temperatura='40',humedad_relativa='100')
    r = ejecutar(client,e,cuerpo)
    assert r.status_code == 201, r.text
    salida = r.json()
    assert D(salida['factor_densidad']) == D('1') and salida['densidad_asumida'] is True
    assert salida['confianza_baja'] is True and salida['alerta_id'] is None
    assert 'SIN_HISTORICO_OCUPACION' in salida['motivos_degradacion']
    assert db_session.execute(text('SELECT count(*) FROM modulo3.alertas WHERE id_activo_biologico=:l'), {'l': e['lote']}).scalar_one() == 0


@pytest.mark.parametrize('densidad,fd,asumida', [(None,'1',True), ('0','0',False), ('3','0.2',False)])
def test_nula_y_valida_conservan_su_comportamiento_sin_leer_historico(client, escenario, monkeypatch, densidad, fd, asumida):
    e = escenario
    configurar(client,e)
    monkeypatch.setattr(OcupacionLoteM02Adapter,'obtener_muestras',lambda *a,**kw: pytest.fail('No corresponde consultar histórico'))
    r = ejecutar(client,e,entrada(e,densidad))
    assert r.status_code == 201, r.text
    assert D(r.json()['factor_densidad']) == D(fd) and r.json()['densidad_asumida'] is asumida
    assert 'SIN_HISTORICO_OCUPACION' not in r.json()['motivos_degradacion']


def test_adaptador_respeta_rls_aunque_la_auditoria_tecnica_no_tiene_rls(db_session, escenario):
    e = escenario
    estado(db_session,e,30,'8')
    estado(db_session,e,30,'999',id_lote=e['externo'])
    db_session.commit()
    db_session.execute(text('SET LOCAL ROLE sgpmp_app'))
    declarar_identidad(db_session,e['vet_id'],'Veterinario')
    assert tuple(db_session.execute(text('SELECT current_user,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')).one()) == ('sgpmp_app',False,False)
    port = OcupacionLoteM02Adapter(db_session)
    ventana = dict(desde=e['instante']-timedelta(days=30),hasta=e['instante'])
    assert port.obtener_muestras(e['lote'],**ventana)
    assert port.obtener_muestras(e['externo'],**ventana) == []
    db_session.execute(text('RESET ROLE'))


def test_el_trigger_real_genera_la_fuente_sin_insercion_manual_de_logs(db_session, escenario):
    e = escenario
    db_session.commit()
    db_session.execute(text('SET LOCAL ROLE sgpmp_app'))
    declarar_identidad(db_session,e['vet_id'],'Veterinario')
    muestras = OcupacionLoteM02Adapter(db_session).obtener_muestras(e['lote'],desde=e['instante']-timedelta(days=30),hasta=e['instante'])
    assert any(m.fecha == e['instante'] and m.densidad == D('9.5') for m in muestras)
    db_session.execute(text('RESET ROLE'))


def test_jwt_rbac_y_finca_ajena_se_validan_antes_del_historico(client, escenario, monkeypatch):
    e = escenario
    configurar(client,e)
    monkeypatch.setattr(OcupacionLoteM02Adapter,'obtener_muestras',lambda *a,**kw: pytest.fail('No debe consultar histórico'))
    assert client.post('/prediccion/riesgo-contagio',json=entrada(e)).status_code == 401
    assert ejecutar(client,e,actor='productor').status_code == 403
    assert ejecutar(client,e,actor='ajeno').status_code == 404


def test_fallo_real_de_persistencia_simulado_revierte_calculo_sin_tocar_historia(client, db_session, escenario, monkeypatch):
    from src.prediction.infrastructure.repositories.resultado_riesgo_contagio_repository import SqlAlchemyResultadoRiesgoContagioRepository
    e = escenario
    ids = [estado(db_session,e,30,'8'),estado(db_session,e,15,'11')]
    configurar(client,e)
    guardar = SqlAlchemyResultadoRiesgoContagioRepository.guardar

    def fallar(self, resultado):
        guardar(self,resultado)
        raise RuntimeError('fallo controlado después del flush')

    with monkeypatch.context() as m:
        m.setattr(SqlAlchemyResultadoRiesgoContagioRepository,'guardar',fallar)
        with pytest.raises(RuntimeError,match='fallo controlado'):
            ejecutar(client,e)
    assert db_session.execute(text('SELECT count(*) FROM modulo4.resultados_riesgo_contagio WHERE id_activo_biologico=:l'), {'l':e['lote']}).scalar_one() == 0
    assert db_session.execute(text('SELECT count(*) FROM auditoria.logs_dml WHERE id_log=ANY(:ids)'), {'ids':ids}).scalar_one() == 2


def test_fallo_del_puerto_no_se_oculta_como_historia_vacia(client, db_session, escenario, monkeypatch):
    from src.shared.errors import ServiceUnavailableError
    e = escenario
    configurar(client,e)

    def fallar(*a,**kw):
        raise ServiceUnavailableError(code='BD_NO_DISPONIBLE',message='Fallo controlado del puerto')

    monkeypatch.setattr(OcupacionLoteM02Adapter,'obtener_muestras',fallar)
    r = ejecutar(client,e)
    assert r.status_code == 503, r.text
    assert db_session.execute(text('SELECT count(*) FROM modulo4.resultados_riesgo_contagio WHERE id_activo_biologico=:l'), {'l':e['lote']}).scalar_one() == 0


def test_la_zona_de_la_sesion_lectora_no_cambia_la_ventana_utc(client, db_session, escenario):
    e = escenario
    estado(db_session,e,30,'8')
    estado(db_session,e,15,'11')
    configurar(client,e)
    db_session.execute(text("SET LOCAL TIME ZONE 'America/Bogota'"))
    r = ejecutar(client,e)
    assert r.status_code == 201, r.text
    assert D(r.json()['factor_densidad']) == D('0.6333')

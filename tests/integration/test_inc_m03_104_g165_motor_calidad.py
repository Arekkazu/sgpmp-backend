# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-26 | Leandro | INC-M03-104-G165 RF-62: verificar escenarios compuestos, historial postcommit/HTTP y rollback con PostgreSQL real y rol API. |
"""El fixture inserta lecturas históricas; el motor, repositorios y HTTP son reales.

No certifica la ingesta del snapshot: esa corrección pertenece a #626.
"""
from datetime import timedelta
from decimal import Decimal
import importlib
import json
import pkgutil
from uuid import uuid4

import pytest
from sqlalchemy import text

from src.configuration.application.use_cases.configuracion_global.configurar_parametros_mlops_use_case import ConfigurarParametrosMLOpsUseCase
from src.prediction.infrastructure.repositories.parametros_mlops_repository import SqlAlchemyParametrosMLOpsRepository
from src.shared.database import como_sistema
from src.telemetry.application.use_cases.calidad.evaluar_calidad_telemetria_use_case import EvaluarCalidadTelemetriaUseCase
from src.telemetry.infrastructure.routers.calidad_router import router
from src.telemetry.infrastructure.workers.postcommit_worker import _lectura

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def rutas_g165(integration_app):
    # main.py registra los modelos al cargar todos sus routers. Esta aplicación
    # acotada también necesita los destinos de las FK del modelo de alertas.
    for paquete in ('src.telemetry.infrastructure.models', 'src.configuration.infrastructure.models',
                    'src.biological_assets.infrastructure.models', 'src.identity_access.infrastructure.models'):
        modulo = importlib.import_module(paquete)
        for item in pkgutil.iter_modules(modulo.__path__, paquete + '.'):
            importlib.import_module(item.name)
    if not any(getattr(r, 'path', None) == '/iot/calidad' for r in integration_app.routes):
        integration_app.include_router(router)


@pytest.fixture
def equipo_g165(db_session, crear_usuario_db, crear_auth_headers):
    admin = crear_usuario_db(id_rol=1)
    headers = crear_auth_headers(admin)
    ConfigurarParametrosMLOpsUseCase(db_session, SqlAlchemyParametrosMLOpsRepository(db_session)).execute(
        {'rf62_k': 3, 'rf62_m': 5, 'rf62_n': 20, 'rf62_p': 5, 'rf62_umbral_drift': 5},
        admin['id_usuario'],
    )
    db_session.execute(text('UPDATE modulo9.configuraciones_globales SET es_activo=false WHERE es_activo'))
    db_session.execute(text('''INSERT INTO modulo9.configuraciones_globales
        (frecuencia_muestreo,heartbeat,fecha_actualizacion,id_usuario,es_activo)
        VALUES (10,20,now(),:u,true)'''), {'u': admin['id_usuario']})
    nombre = 'Calidad ' + uuid4().hex[:10].translate(str.maketrans('0123456789abcdef', 'abcdefghijklmnop'))
    finca = db_session.execute(text('''INSERT INTO modulo9.fincas
        (nombre,ubicacion,tamano_h,fecha_actualizacion,fecha_creacion,es_activo)
        VALUES (:n,'{}',10,now(),now(),true) RETURNING id_finca'''), {'n': nombre}).scalar_one()
    area = db_session.execute(text('''INSERT INTO modulo9.infraestructuras(nombre,id_finca,superficie,es_activo,tipo)
        VALUES (:n,:f,100,true,'Estanque') RETURNING id_infraestructura'''), {'n': nombre, 'f': finca}).scalar_one()
    tipo = db_session.execute(text("""SELECT id_tipo_dispositivo FROM modulo9.tipos_dispositivo_iot
        WHERE categoria='SENSOR' ORDER BY id_tipo_dispositivo LIMIT 1""")).scalar_one()
    dispositivo = db_session.execute(text('''INSERT INTO modulo9.dispositivos_iot
        (serial,descripcion,es_activo,fecha_creacion,id_infraestructura,id_tipo_dispositivo)
        VALUES (:serial,'G165',true,now(),:a,:t) RETURNING id_dispositivo_iot'''),
        {'serial': 'G165-' + uuid4().hex, 'a': area, 't': tipo}).scalar_one()
    sensor = db_session.execute(text('''INSERT INTO modulo9.sensores
        (id_dispositivo_iot,nombre,categoria,es_activo)
        VALUES (:d,:n,'TEMPERATURA',true) RETURNING id_sensores'''),
        {'d': dispositivo, 'n': nombre}).scalar_one()
    db_session.commit()
    return {'sensor': sensor, 'dispositivo': dispositivo, 'headers': headers}


def insertar_serie(db, equipo, valores, actual, *, offset=0, gap=10):
    captura = db.execute(text("SELECT now()-interval '1 minute'")).scalar_one()
    insertar = text('''INSERT INTO modulo3.telemetrias
        (id_sensor,id_variable,id_dispositivo_iot,valor_crudo,valor_ajustado,timestamp_captura,
         timestamp_procesamiento,origen,estado_calidad,calibrado,categoria_variable,unidad_medida,
         valor_agregado,tipo_dato,metadatos,frecuencia_muestreo_min,parametros_calibracion)
        VALUES (:s,9,:d,:v,:ajustado,:ts,now(),'TIEMPO_REAL','LECTURA_VALIDA',true,
                'AMBIENTAL','°C',false,'CRUDO','{}',10,CAST(:snapshot AS jsonb))
        RETURNING id_telemetria''')
    snapshot = json.dumps({'ganancia': 1, 'offset': offset})
    for i, valor in enumerate(valores):
        db.execute(insertar, {'s': equipo['sensor'], 'd': equipo['dispositivo'], 'v': valor,
            'ajustado': Decimal(str(valor)) + Decimal(str(offset)),
            'ts': captura - timedelta(minutes=gap + i * 10), 'snapshot': snapshot})
    identificador = db.execute(insertar, {'s': equipo['sensor'], 'd': equipo['dispositivo'], 'v': actual,
        'ajustado': Decimal(str(actual)) + Decimal(str(offset)), 'ts': captura, 'snapshot': snapshot}).scalar_one()
    db.commit()
    return identificador


def instantanea(db, sensor):
    return db.execute(text('''SELECT jsonb_agg(to_jsonb(t) ORDER BY id_telemetria)
        FROM modulo3.telemetrias t WHERE id_sensor=:s'''), {'s': sensor}).scalar_one()


@pytest.mark.parametrize('serie,valor,offset,gap,indice,clase,flags', [
    pytest.param([19.8, 20.2] * 10, 20, 0, 10, 100, 'APTO', set(), id='base'),
    pytest.param([19.8, 20.2] * 10, 26, 1.5054, 25, 60, 'APTO_CON_RESERVA',
                 {'outlier_estadistico', 'posible_drift', 'gap_temporal_anomalo'}, id='318a'),
    pytest.param([20] * 10 + [19.8, 20.2] * 5, 20, 3.5294, 10, 40, 'APTO_CON_RESERVA',
                 {'sensor_congelado', 'posible_drift'}, id='318b'),
    pytest.param([20] * 20, 26, 0, 10, 0, 'NO_APTO',
                 {'sensor_congelado', 'outlier_estadistico'}, id='318c'),
    pytest.param([20] * 10 + [19.8, 20.2] * 5, 26, 0, 25, 35, 'NO_APTO',
                 {'sensor_congelado', 'outlier_estadistico', 'gap_temporal_anomalo'}, id='320'),
])
def test_http_indices_flags_y_aptitud_reales(
    client, db_session, equipo_g165, serie, valor, offset, gap, indice, clase, flags,
):
    e = equipo_g165
    identificador = insertar_serie(db_session, e, serie, valor, offset=offset, gap=gap)
    antes = instantanea(db_session, e['sensor'])
    response = client.post(f'/iot/calidad/{identificador}/evaluar', headers=e['headers'])
    assert response.status_code == 201, response.text
    ev = response.json()
    assert ev['indice_calidad'] == indice
    assert ev['clasificacion_calidad'] == clase
    assert (ev['apto_para_ia'], ev['apto_para_nic41']) == (clase != 'NO_APTO', clase == 'APTO')
    assert {k for k, v in ev['flags_detectados'].items() if v.get('activo')} == flags
    assert ev['parametros_aplicados']['P'] == 5
    assert ev['parametros_aplicados']['frecuencia_muestreo_min'] == 10
    assert ev['parametros_calibracion_aplicados'] == {'ganancia': 1, 'offset': offset}
    if 'posible_drift' in flags:
        drift = ev['flags_detectados']['posible_drift']
        assert drift['magnitud_drift_porcentaje'] == pytest.approx(15 if offset > 3 else 7, abs=0.001)
    if 'gap_temporal_anomalo' in flags:
        assert ev['flags_detectados']['gap_temporal_anomalo']['gap_real_minutos'] == 25
    if serie == [20] * 20:
        assert ev['flags_detectados']['outlier_estadistico']['magnitud_desviacion'] is None
    almacenada = db_session.execute(text('''SELECT indice_calidad,apto_para_ia,apto_para_nic41,
        flags_detectados FROM modulo3.telemetria_calidad WHERE id_telemetria=:id'''), {'id': identificador}).one()
    assert tuple(almacenada) == (indice, ev['apto_para_ia'], ev['apto_para_nic41'], ev['flags_detectados'])
    detalle = client.get(f'/iot/calidad/{identificador}', headers=e['headers'])
    assert detalle.status_code == 200 and detalle.json()['id_evaluacion'] == ev['id_evaluacion']
    evento = db_session.execute(text('''SELECT resultado,accion_detallada,hash_integridad
        FROM modulo3.bitacora_auditoria_iot WHERE entidad_afectada_id=:id
          AND tipo_evento='EVALUACION_CALIDAD_COMPLETADA' ''') , {'id': str(identificador)}).one()
    assert evento[1]['flags'] == ev['flags_detectados'] and len(evento[2]) == 64
    if offset > 3:
        assert evento[0] == 'PARCIAL'
        assert evento[1]['notificaciones_pendientes'][0]['motivo'] == 'SEVERIDAD_DRIFT_NO_CONFIGURADA'
        assert db_session.execute(text('SELECT count(*) FROM modulo3.alertas WHERE id_sensor=:s'),
                                  {'s': e['sensor']}).scalar_one() == 1
    assert instantanea(db_session, e['sensor']) == antes


def test_postcommit_y_evaluacion_puntual_conservan_cadena_d7(client, db_session, equipo_g165):
    e = equipo_g165
    identificador = insertar_serie(db_session, e, [19.8, 20.2] * 10, 20)
    antes = instantanea(db_session, e['sensor'])
    # Etapa RF-62 real del worker, con identidad de servicio y rol de API.
    with como_sistema(db_session):
        db_session.execute(text('SET LOCAL ROLE sgpmp_app'))
        try:
            _lectura(db_session).evaluar_lectura(identificador)
        finally:
            db_session.execute(text('RESET ROLE'))
    original = db_session.execute(text('''SELECT to_jsonb(c) FROM modulo3.telemetria_calidad c
        WHERE id_telemetria=:id'''), {'id': identificador}).scalar_one()
    assert original['estado_evaluacion'] == 'VIGENTE'
    anterior = original['id_evaluacion']
    for cantidad in (2, 3):
        r = client.post(f'/iot/calidad/{identificador}/evaluar', headers=e['headers'])
        assert r.status_code == 201, r.text
        actual = r.json()
        assert actual['id_evaluacion'] != anterior
        assert actual['id_evaluacion_superada'] == anterior
        filas = db_session.execute(text('''SELECT estado_evaluacion,motivo_reevaluacion
            FROM modulo3.telemetria_calidad WHERE id_telemetria=:id'''), {'id': identificador}).all()
        assert len(filas) == cantidad
        assert sum(f[0] == 'VIGENTE' for f in filas) == 1
        assert all(f[1] for f in filas if f[0] == 'SUPERADA')
        anterior = actual['id_evaluacion']
    historica = db_session.execute(text('''SELECT to_jsonb(c) FROM modulo3.telemetria_calidad c
        WHERE id_evaluacion=CAST(:id AS uuid)'''), {'id': original['id_evaluacion']}).scalar_one()
    assert {k: v for k, v in historica.items() if k not in ('estado_evaluacion', 'motivo_reevaluacion')} == {
        k: v for k, v in original.items() if k not in ('estado_evaluacion', 'motivo_reevaluacion')}
    assert instantanea(db_session, e['sensor']) == antes


def test_fallo_de_auditoria_revierte_nueva_evaluacion_y_superacion(
    client, db_session, equipo_g165, monkeypatch,
):
    e = equipo_g165
    identificador = insertar_serie(db_session, e, [20] * 10 + [19.8, 20.2] * 5, 20, offset=3.5294)
    ruta = f'/iot/calidad/{identificador}/evaluar'
    primera = client.post(ruta, headers=e['headers'])
    assert primera.status_code == 201, primera.text
    original = EvaluarCalidadTelemetriaUseCase._registrar_evidencia
    observadas = []

    def fallar_despues(self, *args, **kwargs):
        original(self, *args, **kwargs)
        observadas.append(True)
        raise RuntimeError('fallo despues de persistir evidencia RF62')

    with monkeypatch.context() as cambios:
        cambios.setattr(EvaluarCalidadTelemetriaUseCase, '_registrar_evidencia', fallar_despues)
        with pytest.raises(RuntimeError, match='persistir evidencia'):
            client.post(ruta, headers=e['headers'])
    assert observadas
    filas = db_session.execute(text('''SELECT id_evaluacion::text,estado_evaluacion
        FROM modulo3.telemetria_calidad WHERE id_telemetria=:id'''), {'id': identificador}).all()
    assert filas == [(primera.json()['id_evaluacion'], 'VIGENTE')]
    assert db_session.execute(text('''SELECT count(*) FROM modulo3.bitacora_auditoria_iot
        WHERE entidad_afectada_id=:id AND tipo_evento='EVALUACION_CALIDAD_COMPLETADA' '''),
        {'id': str(identificador)}).scalar_one() == 1
    assert client.post(ruta, headers=e['headers']).status_code == 201


def test_evaluacion_conserva_jwt_y_rbac(client, db_session, equipo_g165, crear_usuario_db, crear_auth_headers):
    e = equipo_g165
    identificador = insertar_serie(db_session, e, [19.8, 20.2] * 10, 20)
    ruta = f'/iot/calidad/{identificador}/evaluar'
    assert client.post(ruta).status_code == 401
    headers = crear_auth_headers(crear_usuario_db(id_rol=2))
    db_session.commit()
    assert client.post(ruta, headers=headers).status_code == 403
    assert db_session.execute(text('SELECT count(*) FROM modulo3.telemetria_calidad WHERE id_telemetria=:id'),
                              {'id': identificador}).scalar_one() == 0

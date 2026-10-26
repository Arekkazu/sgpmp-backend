# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-26 | Leandro | INC-M03-123-G167 RF-62/RF-22: verificar alta de sensores, rollback y continuidad del flujo con PostgreSQL real. |
"""Reproducción de #626 con JWT/RBAC y las protecciones de TEST_DATABASE_URL.

Los padres se preparan como datos del fixture; el sensor se registra por HTTP.
No se reemplazan entidades, repositorios ni casos de uso del alta.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import event, text

from src.configuration.application.use_cases.configuracion_global.configurar_parametros_mlops_use_case import ConfigurarParametrosMLOpsUseCase
from src.configuration.domain.entities import sensor_area as dominio_asociacion
from src.configuration.infrastructure.routers.dispositivo_iot_router import router as dispositivos
from src.configuration.infrastructure.routers.sensor_router import router as sensores
from src.configuration.infrastructure.models.sensor_model import SensorModel
from src.prediction.infrastructure.repositories.parametros_mlops_repository import SqlAlchemyParametrosMLOpsRepository
from src.shared.database import como_sistema
from src.shared.errors import InfrastructureError
from src.telemetry.infrastructure.routers.calidad_router import router as calidad
from src.telemetry.infrastructure.routers.telemetria_router import router as telemetria

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def rutas_g167(integration_app):
    for router in (dispositivos, sensores, calidad, telemetria):
        if not any(getattr(r, 'path', None) == router.routes[0].path for r in integration_app.routes):
            integration_app.include_router(router)


@pytest.fixture
def escenario_sensor(db_session):
    sufijo = uuid4().hex[:10].translate(str.maketrans('0123456789abcdef', 'abcdefghijklmnop'))
    finca = db_session.execute(text("""
        INSERT INTO modulo9.fincas
            (nombre,ubicacion,tamano_h,fecha_actualizacion,fecha_creacion,es_activo)
        VALUES (:nombre,'{"departamento":"Huila","municipio":"Neiva","vereda":"Centro",
                "latitud":"2.93","longitud":"-75.28"}'::jsonb,10,now(),now(),true)
        RETURNING id_finca
    """), {'nombre': 'Finca Sensor ' + sufijo}).scalar_one()
    area = db_session.execute(text("""
        INSERT INTO modulo9.infraestructuras (nombre,id_finca,superficie,es_activo,tipo)
        VALUES (:nombre,:finca,100,true,'Estanque') RETURNING id_infraestructura
    """), {'nombre': 'Area Sensor ' + sufijo, 'finca': finca}).scalar_one()
    tipo = db_session.execute(text("""
        SELECT id_tipo_dispositivo FROM modulo9.tipos_dispositivo_iot
        WHERE categoria='SENSOR' ORDER BY id_tipo_dispositivo LIMIT 1
    """)).scalar_one()
    serial = 'G167-' + uuid4().hex
    dispositivo = db_session.execute(text("""
        INSERT INTO modulo9.dispositivos_iot
            (serial,descripcion,es_activo,fecha_creacion,id_infraestructura,id_tipo_dispositivo)
        VALUES (:serial,'Dispositivo G167',true,now(),:area,:tipo)
        RETURNING id_dispositivo_iot
    """), {'serial': serial, 'area': area, 'tipo': tipo}).scalar_one()
    return {'finca': finca, 'area': area, 'dispositivo': dispositivo, 'serial': serial,
            'nombre': 'Sensor ' + sufijo}


def _ruta(e):
    return f"/configuracion/dispositivos-iot/{e['dispositivo']}/sensores"


@pytest.mark.parametrize('categoria', ['TEMPERATURA', None])
def test_payload_valido_crea_sensor_activo_sin_exponer_es_activo(
    client, db_session, escenario_sensor, crear_usuario_db, crear_auth_headers, categoria,
):
    e = escenario_sensor
    headers = crear_auth_headers(crear_usuario_db(id_rol=1))
    body = {'nombre': e['nombre']}
    if categoria is not None:
        body['categoria'] = categoria
    respuesta = client.post(_ruta(e), json=body, headers=headers)
    assert respuesta.status_code == 201, respuesta.text
    sensor = respuesta.json()
    assert sensor['id_sensores'] > 0
    assert sensor['nombre'] == body['nombre']
    assert sensor['categoria'] == categoria
    assert sensor['es_activo'] is True
    assert sensor['id_dispositivo_iot'] == e['dispositivo']
    fila = db_session.execute(text("""
        SELECT es_activo,nombre,categoria::text FROM modulo9.sensores WHERE id_sensores=:id
    """), {'id': sensor['id_sensores']}).one()
    assert tuple(fila) == (True, body['nombre'], categoria)
    listado = client.get(_ruta(e), headers=headers)
    assert listado.status_code == 200, listado.text
    assert listado.json() == {'total': 1, 'items': [sensor]}


@pytest.mark.parametrize('fallo', ['flush', 'commit'])
def test_fallo_transaccional_no_deja_sensor_parcial(
    client, db_session, escenario_sensor, crear_usuario_db, crear_auth_headers, monkeypatch, fallo,
):
    e = escenario_sensor
    headers = crear_auth_headers(crear_usuario_db(id_rol=1))
    db_session.commit()  # El setup debe sobrevivir al rollback del caso de uso.
    original_flush = db_session.flush
    original_commit = db_session.commit
    inserciones = []

    def observar_insert(_mapper, _connection, sensor):
        inserciones.append(sensor.id_sensores)

    def fallar_flush(*args, **kwargs):
        nuevo_sensor = any(type(obj).__name__ == 'SensorModel' for obj in db_session.new)
        original_flush(*args, **kwargs)
        if nuevo_sensor:
            raise RuntimeError('fallo inducido despues del INSERT del sensor')

    def fallar_commit():
        if inserciones:
            raise InfrastructureError('ERROR_INTERNO', 'Fallo controlado de confirmacion.')
        original_commit()

    event.listen(SensorModel, 'after_insert', observar_insert)
    try:
        with monkeypatch.context() as cambios:
            cambios.setattr(db_session, fallo, fallar_flush if fallo == 'flush' else fallar_commit)
            respuesta = client.post(_ruta(e), json={'nombre': e['nombre'], 'categoria': 'TEMPERATURA'}, headers=headers)
    finally:
        event.remove(SensorModel, 'after_insert', observar_insert)
    assert inserciones, 'El fallo debe ocurrir despues de insertar realmente el sensor.'
    assert respuesta.status_code == 500
    assert respuesta.json()['error_code'] == 'ERROR_INTERNO'
    assert 'INSERT' not in respuesta.text and 'RuntimeError' not in respuesta.text
    assert db_session.execute(text(
        'SELECT count(*) FROM modulo9.sensores WHERE id_dispositivo_iot=:id'
    ), {'id': e['dispositivo']}).scalar_one() == 0
    reintento = client.post(_ruta(e), json={'nombre': e['nombre'], 'categoria': 'TEMPERATURA'}, headers=headers)
    assert reintento.status_code == 201, reintento.text


def test_ingeniero_asignado_crea_y_ajeno_no_accede(
    client, db_session, escenario_sensor, crear_usuario_db, crear_auth_headers,
):
    e = escenario_sensor
    ingeniero = crear_usuario_db(id_rol=4)
    headers = crear_auth_headers(ingeniero)
    db_session.commit()
    body = {'nombre': e['nombre'], 'categoria': 'TEMPERATURA'}
    ajeno = client.post(_ruta(e), json=body, headers=headers)
    assert ajeno.status_code == 404, ajeno.text
    db_session.execute(text(
        'INSERT INTO modulo9.usuarios_fincas (id_usuario,id_finca) VALUES (:usuario,:finca)'
    ), {'usuario': ingeniero['id_usuario'], 'finca': e['finca']})
    db_session.commit()
    asignado = client.post(_ruta(e), json=body, headers=headers)
    assert asignado.status_code == 201, asignado.text
    assert asignado.json()['es_activo'] is True


@pytest.mark.parametrize('offset,hay_drift', [(0, False), (2, True)])
def test_sensor_nuevo_continua_por_asociacion_calibracion_ingesta_y_calidad(
    client, db_session, escenario_sensor, crear_usuario_db, crear_auth_headers,
    headers_broker, offset, hay_drift, monkeypatch,
):
    e = escenario_sensor
    admin = crear_usuario_db(id_rol=1)
    headers = crear_auth_headers(admin)
    ConfigurarParametrosMLOpsUseCase(
        db_session, SqlAlchemyParametrosMLOpsRepository(db_session),
    ).execute({'rf62_k': 3, 'rf62_m': 5, 'rf62_n': 20,
               'rf62_umbral_drift': 5, 'rf62_p': 3}, admin['id_usuario'])
    db_session.execute(text("""
        INSERT INTO modulo9.configuraciones_globales
            (frecuencia_muestreo,heartbeat,fecha_actualizacion,id_usuario,es_activo)
        VALUES (5,10,now(),:usuario,true)
    """), {'usuario': admin['id_usuario']})
    db_session.commit()

    alta = client.post(_ruta(e), json={'nombre': e['nombre'], 'categoria': 'TEMPERATURA'}, headers=headers)
    assert alta.status_code == 201, alta.text
    sensor = alta.json()['id_sensores']
    ruta_sensor = f'/configuracion/sensores/{sensor}'
    # El fixture conserva una transaccion exterior: now() de PostgreSQL queda
    # fijo. Simular el paso del tiempo en el reloj de la asociacion permite
    # probar una serie historica posterior a ella sin quitar sus validaciones.
    captura = db_session.execute(text('SELECT now()')).scalar_one().astimezone(timezone.utc) - timedelta(minutes=1)

    class RelojAsociacion(datetime):
        @classmethod
        def now(cls, tz=None):
            instante = captura - timedelta(hours=3)
            return instante.astimezone(tz) if tz else instante.replace(tzinfo=None)

    with monkeypatch.context() as reloj:
        reloj.setattr(dominio_asociacion, 'datetime', SimpleNamespace(datetime=RelojAsociacion, timezone=timezone))
        asociacion = client.post(ruta_sensor + '/asociar', json={
            'id_dispositivo_iot': e['dispositivo'], 'id_infraestructura': e['area'],
            'punto_instalacion': 'Punto Sensor',
        }, headers=headers)
    assert asociacion.status_code == 201, asociacion.text
    calibracion = client.post(ruta_sensor + '/calibrar', json={
        'id_dispositivo_iot': e['dispositivo'], 'id_infraestructura': e['area'],
        'valor_referencia': 22, 'ganancia': 1, 'offset': offset,
        'fecha_calibracion': (captura - timedelta(hours=2)).isoformat(),
        'modo_calibracion': 'SENSOR',
    }, headers=headers)
    assert calibracion.status_code == 201, calibracion.text

    # La ingesta usa la identidad de servicio existente y el mismo rol de API.
    # Comprobar sus precondiciones sin conceder acceso global ni usar BYPASSRLS.
    with como_sistema(db_session):
        db_session.execute(text('SET LOCAL ROLE sgpmp_app'))
        try:
            contexto = db_session.execute(text("""
                SELECT current_user AS rol,
                       current_setting('app.current_user_id') AS usuario,
                       modulo3.fn_validar_dispositivo(:dispositivo,:sensor) AS valido,
                       (SELECT es_activo FROM modulo9.dispositivos_iot
                        WHERE id_dispositivo_iot=:dispositivo) AS dispositivo_activo,
                       (SELECT es_activo FROM modulo9.sensores WHERE id_sensores=:sensor) AS sensor_activo
            """), {'dispositivo': e['dispositivo'], 'sensor': sensor}).mappings().one()
        finally:
            db_session.execute(text('RESET ROLE'))
    assert contexto['valido'] is True, dict(contexto)

    for indice in range(21):
        ingesta = client.post('/iot/telemetria', json={
            'device_id': e['dispositivo'], 'sensor_id': sensor, 'serial': e['serial'],
            'tipo_variable': 'TEMPERATURA_AMBIENTAL', 'valor': 22 + indice % 2,
            'unidad': '°C', 'timestamp_captura': (captura - timedelta(minutes=20-indice)).isoformat(),
        }, headers=headers_broker)
        assert ingesta.status_code == 201, ingesta.text
        assert ingesta.json()['estado_calidad'] == 'LECTURA_VALIDA'
    id_lectura = ingesta.json()['id_telemetria']
    antes = db_session.execute(text(
        'SELECT to_jsonb(t) FROM modulo3.telemetrias t WHERE id_telemetria=:id'
    ), {'id': id_lectura}).scalar_one()
    assert antes['calibrado'] is True
    assert antes['valor_ajustado'] == 22 + offset
    respuesta = client.post(f'/iot/calidad/{id_lectura}/evaluar', headers=headers)
    assert respuesta.status_code == 201, respuesta.text
    resultado = respuesta.json()
    assert resultado['id_sensor'] == sensor
    assert resultado['parametros_aplicados']['N'] == 20
    assert resultado['parametros_calibracion_aplicados'] is not None, (
        'RF-53 ajusto la lectura pero no conservo el snapshot de calibracion que necesita RF-62.'
    )
    assert resultado['parametros_calibracion_aplicados']['offset'] == offset
    assert bool(resultado['flags_detectados'].get('posible_drift', {}).get('activo')) is hay_drift
    assert resultado['indice_calidad'] == (70 if hay_drift else 100)
    detalle = client.get(f'/iot/calidad/{id_lectura}', headers=headers)
    assert detalle.status_code == 200, detalle.text
    assert detalle.json()['id_evaluacion'] == resultado['id_evaluacion']
    assert db_session.execute(text(
        'SELECT to_jsonb(t) FROM modulo3.telemetrias t WHERE id_telemetria=:id'
    ), {'id': id_lectura}).scalar_one() == antes


def test_alta_sigue_exigiendo_jwt_y_permiso(
    client, db_session, escenario_sensor, crear_usuario_db, crear_auth_headers,
):
    e = escenario_sensor
    body = {'nombre': e['nombre'], 'categoria': 'TEMPERATURA'}
    assert client.post(_ruta(e), json=body).status_code == 401
    usuario = crear_usuario_db(id_rol=2)
    headers = crear_auth_headers(usuario)
    db_session.execute(text(
        'UPDATE modulo1.permisos SET es_activo=false WHERE id_rol=2 AND id_recurso=11 AND id_accion=1'
    ))
    db_session.commit()
    respuesta = client.post(_ruta(e), json=body, headers=headers)
    assert respuesta.status_code == 403, respuesta.text
    assert db_session.execute(text(
        'SELECT count(*) FROM modulo9.sensores WHERE id_dispositivo_iot=:id'
    ), {'id': e['dispositivo']}).scalar_one() == 0


def test_dispositivo_inexistente_conserva_404(client, crear_usuario_db, crear_auth_headers):
    headers = crear_auth_headers(crear_usuario_db(id_rol=1))
    respuesta = client.post('/configuracion/dispositivos-iot/2147483647/sensores',
                            json={'nombre': 'Sensor G167', 'categoria': 'TEMPERATURA'}, headers=headers)
    assert respuesta.status_code == 404, respuesta.text
    assert respuesta.json()['error_code'] == 'DISPOSITIVO_NO_ENCONTRADO'


def test_categoria_invalida_se_rechaza_antes_de_persistir(
    client, db_session, escenario_sensor, crear_usuario_db, crear_auth_headers,
):
    e = escenario_sensor
    headers = crear_auth_headers(crear_usuario_db(id_rol=1))
    respuesta = client.post(_ruta(e), json={'nombre': e['nombre'], 'categoria': 'NO_CATALOGADA'}, headers=headers)
    assert respuesta.status_code == 400, respuesta.text
    assert respuesta.json()['error_code'] == 'VAL_ENTRADA'
    assert db_session.execute(text(
        'SELECT count(*) FROM modulo9.sensores WHERE id_dispositivo_iot=:id'
    ), {'id': e['dispositivo']}).scalar_one() == 0

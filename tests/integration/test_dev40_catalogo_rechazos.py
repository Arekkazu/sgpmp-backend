# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-40 RF-53: verifica catalogo y bitacora en PG  |
"""HTTP, catálogo M09 y bitácora reales en PostgreSQL exclusivo de pruebas."""
from datetime import datetime, timedelta, timezone
import importlib
from pathlib import Path
import pkgutil
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
import pytest

from src.shared.database import get_db_sistema
from src.shared.error_handlers import register_error_handlers
from src.shared.middlewares import RequestContextMiddleware
from src.telemetry.infrastructure.adapters.variable_catalogo_m09_adapter import VariableCatalogoM09Adapter
from src.telemetry.infrastructure.routers import telemetria_router, ruta_ingesta_auditada

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def modelos():
    for paquete in ('src.configuration.infrastructure.models', 'src.biological_assets.infrastructure.models',
                    'src.telemetry.infrastructure.models', 'src.identity_access.infrastructure.models'):
        module = importlib.import_module(paquete)
        for item in pkgutil.iter_modules(module.__path__, paquete + '.'):
            importlib.import_module(item.name)


def _crear_equipo(db_session):
    tag = uuid4().hex[:12]
    area = db_session.execute(text('''WITH finca AS (
        INSERT INTO modulo9.fincas(nombre,ubicacion,tamano_h,es_activo,fecha_creacion,fecha_actualizacion)
        VALUES (:nombre,'{}',10,true,now(),now()) RETURNING id_finca)
        INSERT INTO modulo9.infraestructuras(nombre,id_finca,superficie,es_activo,tipo)
        SELECT :nombre,id_finca,100,true,'Estanque' FROM finca RETURNING id_infraestructura
    '''), {'nombre': 'Catalogo ' + ''.join(chr(97+int(c,16)) for c in tag)}).scalar_one()
    device = db_session.execute(text('''INSERT INTO modulo9.dispositivos_iot
        (serial,descripcion,es_activo,fecha_creacion,id_infraestructura,id_tipo_dispositivo)
        VALUES (:serial,'DEV-40',true,now(),:area,3) RETURNING id_dispositivo_iot
    '''), {'serial': tag, 'area': area}).scalar_one()
    sensor = db_session.execute(text('''INSERT INTO modulo9.sensores(id_dispositivo_iot,es_activo,nombre)
        VALUES (:device,true,'Sensor catalogo') RETURNING id_sensores
    '''), {'device': device}).scalar_one()
    db_session.commit()
    return dict(device=device, sensor=sensor, serial=tag)


@pytest.fixture
def equipo(db_session):
    return _crear_equipo(db_session)


@pytest.fixture
def http(db_session, integration_engine, headers_broker, monkeypatch):
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)
    app.include_router(telemetria_router.router)
    app.dependency_overrides[get_db_sistema] = lambda: db_session
    # Sesión/conexión realmente independiente de la transacción del request.
    monkeypatch.setattr(ruta_ingesta_auditada, 'SessionLocal', sessionmaker(bind=integration_engine))
    with TestClient(app, headers=headers_broker, raise_server_exceptions=False) as client:
        yield client


def payload(equipo, **cambios):
    return dict(dict(device_id=equipo['device'], sensor_id=equipo['sensor'], serial=equipo['serial'],
        tipo_variable='TEMPERATURA_AMBIENTAL', valor='22.5', unidad='°C',
        timestamp_captura=(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()), **cambios)


def nueva_variable(db, **cambios):
    datos = dict(nombre='Variable ' + uuid4().hex[:12], codigo='DEV40_' + uuid4().hex[:12].upper(),
        categoria='AMBIENTAL', unidad='ud', activo=True)
    datos.update(cambios)
    datos['id'] = db.execute(text('''INSERT INTO modulo9.variables_ambientales
        (nombre,unidad,valor_fisico_min,valor_fisico_max,es_activo,codigo_telemetria,categoria_variable)
        VALUES (:nombre,:unidad,0,100,:activo,:codigo,:categoria) RETURNING id_variable_ambiental
    '''), datos).scalar_one()
    db.commit()
    return datos


def test_catalogo_existente_nombre_y_codigos_historicos(db_session):
    adapter = VariableCatalogoM09Adapter(db_session)
    for codigo, alias in [('TEMP_CORPORAL', 'TEMPERATURA_CORPORAL'), ('ACTIVIDAD', 'ACTIVIDAD_MOVIMIENTO'),
                          ('TDS', 'CONDUCTIVIDAD_ELECTRICA'), ('CO2', 'DIOXIDO_DE_CARBONO_CO2')]:
        regla = adapter.obtener_regla(codigo)
        assert regla is not None and adapter.obtener_regla(alias).id_variable == regla.id_variable


def test_variable_nueva_se_acepta_sin_recrear_el_consumidor(http, db_session, equipo):
    # El mismo adaptador ya fue consultado antes de insertar otra variable.
    adapter = VariableCatalogoM09Adapter(db_session)
    assert adapter.obtener_regla('NUEVA_VARIABLE_DEV40') is None
    variable = nueva_variable(db_session, codigo='NUEVA_VARIABLE_DEV40', categoria='HIDRICA')
    assert adapter.obtener_regla('NUEVA_VARIABLE_DEV40').id_variable == variable['id']
    response = http.post('/iot/telemetria', json=payload(equipo, tipo_variable=variable['codigo'],
        id_variable=variable['id'], categoria_variable='HIDRICA', unidad=variable['unidad']))
    assert response.status_code == 201, response.text
    lectura = db_session.execute(text('''SELECT id_variable,categoria_variable::text,unidad_medida FROM modulo3.telemetrias
        WHERE id_telemetria=:id'''), {'id': response.json()['id_telemetria']}).one()
    assert lectura == (variable['id'], 'HIDRICA', 'ud')


def test_cambios_catalogo_se_reconocen_en_ingesta_sin_reiniciar(http, db_session, equipo):
    variable = nueva_variable(db_session)
    assert http.post('/iot/telemetria', json=payload(equipo, tipo_variable=variable['codigo'], unidad='ud')).status_code == 201
    db_session.execute(text("UPDATE modulo9.variables_ambientales SET unidad='nueva', categoria_variable='ANIMAL' WHERE id_variable_ambiental=:id"), variable)
    db_session.commit()
    segunda = payload(equipo, tipo_variable=variable['codigo'], unidad='nueva',
        timestamp_captura=(datetime.now(timezone.utc)-timedelta(seconds=30)).isoformat())
    response = http.post('/iot/telemetria', json=segunda)
    assert response.status_code == 201, response.text
    fila = db_session.execute(text('''SELECT categoria_variable::text,unidad_medida FROM modulo3.telemetrias
        WHERE id_telemetria=:id'''), {'id': response.json()['id_telemetria']}).one()
    assert fila == ('ANIMAL', 'nueva')


@pytest.mark.parametrize('cambio,codigo,estado', [
    ({'tipo_variable': 'NO_EXISTE_DEV40'}, 'VARIABLE_NO_ENCONTRADA', 404),
    ({'id_variable': 2147483000}, 'VARIABLE_INCOMPATIBLE', 400),
    ({'categoria_variable': 'ANIMAL'}, 'VARIABLE_INCOMPATIBLE', 400),
    ({'unidad': 'invalida'}, 'ERROR_UNIDAD', 400),
])
def test_rechazo_catalogo_o_unidad_conserva_clasificacion(http, db_session, equipo, cambio, codigo, estado):
    response = http.post('/iot/telemetria', json=payload(equipo, **cambio))
    assert response.status_code == estado and response.json()['error_code'] == codigo, response.text
    assert db_session.execute(text('SELECT count(*) FROM modulo3.telemetrias WHERE id_sensor=:s'), {'s': equipo['sensor']}).scalar_one() == 0
    registros = db_session.execute(text('SELECT estado_calidad::text FROM modulo3.bitacora_ingest WHERE id_sensor=:s'), {'s': equipo['sensor']}).scalars().all()
    assert len(registros) == 1 and registros[0] != 'ERROR_ESTRUCTURA'


def test_variable_inactiva_no_se_acepta(http, db_session, equipo):
    variable = nueva_variable(db_session, activo=False)
    response = http.post('/iot/telemetria', json=payload(equipo, tipo_variable=variable['codigo'], unidad='ud'))
    assert response.status_code == 404


def test_nombre_catalogo_sin_codigo_opcional_se_reconoce_dinamicamente(http, db_session, equipo):
    variable = nueva_variable(db_session, nombre='Medicion Dinamica Nueva', codigo=None)
    response = http.post('/iot/telemetria', json=payload(equipo, tipo_variable='MEDICION_DINAMICA_NUEVA', unidad='ud'))
    assert response.status_code == 201, response.text
    assert VariableCatalogoM09Adapter(db_session).obtener_regla('MEDICION_DINAMICA_NUEVA').id_variable == variable['id']


def test_catalogo_sin_categoria_falla_como_configuracion(http, db_session, equipo):
    variable = nueva_variable(db_session, categoria=None)
    response = http.post('/iot/telemetria', json=payload(equipo, tipo_variable=variable['codigo'], unidad='ud'))
    assert response.status_code == 503 and response.json()['error_code'] == 'CATALOGO_INCOMPLETO'
    assert db_session.execute(text('SELECT count(*) FROM modulo3.bitacora_ingest WHERE id_sensor=:s'), {'s': equipo['sensor']}).scalar_one() == 0


def test_fallo_real_de_conexion_catalogo_es_503_sin_error_estructura(http, db_session, equipo, monkeypatch):
    engine_sin_servicio = create_engine('postgresql+psycopg2://postgres@127.0.0.1:1/sgpmp_dev40_test', connect_args={'connect_timeout': 1})
    construir = telemetria_router._build_use_case
    try:
        with Session(engine_sin_servicio) as conexion_catalogo:
            def con_catalogo_inaccesible(db):
                caso = construir(db)
                caso.catalogo_port = VariableCatalogoM09Adapter(conexion_catalogo)
                return caso
            monkeypatch.setattr(telemetria_router, '_build_use_case', con_catalogo_inaccesible)
            response = http.post('/iot/telemetria', json=payload(equipo))
        assert response.status_code == 503 and response.json()['error_code'] == 'BD_NO_DISPONIBLE'
        assert db_session.execute(text('SELECT count(*) FROM modulo3.telemetrias WHERE id_sensor=:s'), {'s': equipo['sensor']}).scalar_one() == 0
        assert db_session.execute(text('SELECT count(*) FROM modulo3.bitacora_ingest WHERE id_sensor=:s'), {'s': equipo['sensor']}).scalar_one() == 0
    finally:
        engine_sin_servicio.dispose()


@pytest.mark.parametrize('ruta', ['/iot/telemetria', '/iot/telemetria/batch'])
def test_estructura_400_persiste_auditoria_independiente_sin_telemetria(http, db_session, integration_engine, equipo, ruta):
    correlacion = str(uuid4())
    previo = db_session.execute(text('SELECT count(*) FROM modulo3.telemetrias')).scalar_one()
    body = dict(device_id=equipo['device'], sensor_id=equipo['sensor'], access_key='secreto-DEV40', valor='secreto-valor')
    if ruta.endswith('/batch'):
        body = {'registros': [payload(equipo), body], 'idempotency_key': 'secreto-idempotencia'}
    response = http.post(ruta, json=body, headers={'X-Request-ID': correlacion})
    assert response.status_code == 400 and response.json()['error_code'] == 'VAL_ENTRADA'
    assert db_session.execute(text('SELECT count(*) FROM modulo3.telemetrias')).scalar_one() == previo
    db_session.rollback()
    with integration_engine.connect() as otra:
        filas = otra.execute(text('''SELECT estado_calidad::text,tipo_evento::text,payload_recibido,id_telemetria
            FROM modulo3.bitacora_ingest WHERE payload_recibido->>'id_correlacion'=:id'''), {'id': correlacion}).all()
    assert len(filas) == 1
    estado, evento, detalle, id_lectura = filas[0]
    assert estado == 'ERROR_ESTRUCTURA' and evento == 'ERROR_PROCESAMIENTO' and id_lectura is None
    assert detalle['resultado'] == 'RECHAZADO' and detalle['endpoint'] == ruta
    assert 'secreto' not in repr(detalle) and 'Authorization' not in repr(detalle)


def test_json_invalido_se_registra_una_vez_por_intento(http, integration_engine):
    correlacion = str(uuid4())
    response = http.post('/iot/telemetria', content='{"token":"secreto",',
        headers={'X-Request-ID': correlacion, 'Content-Type': 'application/json'})
    assert response.status_code == 400
    with integration_engine.connect() as db:
        filas = db.execute(text("SELECT payload_recibido FROM modulo3.bitacora_ingest WHERE payload_recibido->>'id_correlacion'=:id"), {'id': correlacion}).scalars().all()
    assert len(filas) == 1 and 'secreto' not in repr(filas)


def test_ids_inexistentes_no_impiden_persistir_rechazo_estructural(http, integration_engine):
    correlacion = str(uuid4())
    response = http.post('/iot/telemetria', json={'device_id': 2147483000, 'sensor_id': 2147483000},
        headers={'X-Request-ID': correlacion})
    assert response.status_code == 400
    with integration_engine.connect() as db:
        fila = db.execute(text('''SELECT id_sensor,id_dispositivo_iot,payload_recibido
            FROM modulo3.bitacora_ingest WHERE payload_recibido->>'id_correlacion'=:id'''), {'id': correlacion}).one()
    assert fila[0] is None and fila[1] is None
    assert fila[2]['device_id'] == 2147483000 and fila[2]['sensor_id'] == 2147483000


def test_referencias_confirmadas_se_enlazan_en_auditoria_independiente(http, integration_engine):
    with Session(integration_engine) as preparacion:
        equipo = _crear_equipo(preparacion)
    correlacion = str(uuid4())
    response = http.post('/iot/telemetria', json={'device_id': equipo['device'], 'sensor_id': equipo['sensor']},
        headers={'X-Request-ID': correlacion})
    assert response.status_code == 400
    with integration_engine.connect() as db:
        fila = db.execute(text('''SELECT id_sensor,id_dispositivo_iot FROM modulo3.bitacora_ingest
            WHERE payload_recibido->>'id_correlacion'=:id'''), {'id': correlacion}).one()
    assert fila == (equipo['sensor'], equipo['device'])


def test_batch_con_variable_nueva_y_duplicado_conserva_ingesta(http, db_session, equipo):
    variable = nueva_variable(db_session)
    item = payload(equipo, tipo_variable=variable['codigo'], unidad='ud')
    response = http.post('/iot/telemetria/batch', json={'registros': [item, item]})
    assert response.status_code == 200, response.text
    assert (response.json()['aceptados'], response.json()['duplicados']) == (1, 1)


def test_migracion_preserva_definiciones_existentes_y_es_reversible(db_session):
    spec = importlib.util.spec_from_file_location('dev40_migracion', Path(__file__).parents[2] / 'alembic/versions/f40c53a37834_dev40_rf53_catalogo_dinamico.py')
    migracion = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migracion)
    consulta = text('''SELECT id_variable_ambiental,nombre,unidad,valor_fisico_min,valor_fisico_max,es_activo,es_critica
        FROM modulo9.variables_ambientales ORDER BY id_variable_ambiental''')
    antes = db_session.execute(consulta).all()
    with Operations.context(MigrationContext.configure(db_session.connection())):
        migracion.downgrade()
        assert db_session.execute(consulta).all() == antes
        migracion.upgrade()
        assert db_session.execute(consulta).all() == antes
    assert VariableCatalogoM09Adapter(db_session).obtener_regla('TEMPERATURA_AMBIENTAL').categoria == 'AMBIENTAL'

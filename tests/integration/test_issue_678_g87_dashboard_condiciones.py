# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-26 | Leandro | ISSUE-678 G87 RF-58: validar ingesta SQL, proyección HTTP, permisos y aislamiento con PostgreSQL real. |
"""No usa MQTT ni despliegue TEST: ingesta por la frontera SQL real y HTTP local con JWT."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import importlib.util
from pathlib import Path
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from src.shared.database import get_db, declarar_identidad
from src.shared.error_handlers import register_error_handlers
from src.shared import jwt as jwt_module
from src.telemetry.infrastructure.routers.monitoreo_router import router
from src.telemetry.infrastructure.repositories.ingesta_telemetria_repository import SqlAlchemyIngestaTelemetriaRepository
from src.telemetry.infrastructure.repositories.monitoreo_repository import SqlAlchemyMonitoreoRepository

_spec = importlib.util.spec_from_file_location('g87_base', Path(__file__).with_name('test_dev05_ingesta_bplus_postcommit.py'))
h = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h)
modelos = h.modelos
pytestmark = pytest.mark.integration


@pytest.fixture
def contexto(db_session, crear_usuario_db, crear_auth_headers):
    db = db_session
    equipo = h.hardware(db)
    uid, rol = db.execute(text('SELECT u.id_usuario,r.nombre_rol FROM modulo1.usuarios u JOIN modulo1.roles r USING(id_rol) ORDER BY u.id_usuario LIMIT 1')).one()
    declarar_identidad(db, uid, rol)
    especie = db.execute(text("INSERT INTO modulo9.especies(nombre,descripcion,fecha_creacion,es_activo) VALUES(:n,'G87',now(),true) RETURNING id_especie"), {'n':'Especie '+''.join(chr(97+int(c,16)) for c in uuid.uuid4().hex[:12])}).scalar_one()
    db.execute(text('INSERT INTO modulo9.infraestructuras_especies(id_infraestructura,id_especie) VALUES(:a,:e)'), {'a':equipo['area'],'e':especie})
    umbral = db.execute(text("""INSERT INTO modulo9.umbrales_ambientales(id_especie,id_variable_ambiental,unidad_medida,valor_min,valor_max,es_activo,fecha_actualizacion,id_usuario)
        VALUES(:e,9,'°C',15,30,true,now(),:u) RETURNING id_umbral_ambiental"""), {'e':especie,'u':uid}).scalar_one()
    for nivel,a,b in [('normal',15,25),('precaucion',25,28),('critico',28,30)]:
        db.execute(text('INSERT INTO modulo9.niveles_alerta_ambientales(id_umbral_ambiental,nivel,limite_inferior,limite_superior) VALUES(:i,:n,:a,:b)'), {'i':umbral,'n':nivel,'a':a,'b':b})
    finca = db.execute(text('SELECT id_finca FROM modulo9.infraestructuras WHERE id_infraestructura=:a'), {'a':equipo['area']}).scalar_one()
    headers = {}
    for nombre in ['Productor','Ingeniero de Campo','Contador']:
        id_rol = db.execute(text('SELECT id_rol FROM modulo1.roles WHERE nombre_rol=:n'), {'n':nombre}).scalar_one()
        usuario = crear_usuario_db(id_rol=id_rol)
        numero = db.execute(text('SELECT COALESCE(max(id_usuario_finca),0)+1 FROM modulo9.usuarios_fincas')).scalar_one()
        db.execute(text('INSERT INTO modulo9.usuarios_fincas(id_usuario_finca,id_usuario,id_finca,es_activo) VALUES(:i,:u,:f,true)'), {'i':numero,'u':usuario['id_usuario'],'f':finca})
        headers[nombre] = crear_auth_headers(usuario)
    db.commit()
    return equipo | {'headers':headers, 'base':datetime.now(timezone.utc)-timedelta(minutes=8), 'finca':finca}


@pytest.fixture
def cliente(db_session, monkeypatch):
    monkeypatch.setattr(jwt_module, '_SECRET_KEY', 'sgpmp-integration-tests-only')
    monkeypatch.setattr(jwt_module, '_EXPIRE_HOURS', 8)
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    def conexion():
        db_session.info.clear()
        db_session.execute(text('SET LOCAL ROLE sgpmp_app'))
        assert db_session.execute(text('SELECT current_user')).scalar_one() == 'sgpmp_app'
        try:
            yield db_session
        finally:
            db_session.execute(text('RESET ROLE'))
    app.dependency_overrides[get_db] = conexion
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def ingerir(db, ctx, valor, minuto):
    ts=ctx['base']+timedelta(minutes=minuto)
    result=SqlAlchemyIngestaTelemetriaRepository(db).ingerir(dict(device_id=ctx['device'],sensor_id=ctx['sensor'],id_variable=9,
        categoria='AMBIENTAL',valor=Decimal(str(valor)),unidad='°C',timestamp_captura=ts,timestamp_envio=ts,
        origen='TIEMPO_REAL',tipo_dato='CRUDO',valor_agregado=False,ventana_agregacion=None,latitud=None,longitud=None,
        nivel_bateria=77,calidad_senal_rssi=-83,calidad_senal_snr=4.5,estado_conectividad=True,metadatos={}))
    db.commit()
    return result


def dashboard(cliente, ctx, rol):
    r=cliente.get('/iot/monitoreo/dashboard/'+str(ctx['area']),headers=ctx['headers'][rol])
    assert r.status_code==200,r.text
    datos=r.json()
    assert datos['total']==1
    return datos['sensores'][0]


def validas(db,ctx):
    h.calibrar(db,ctx)
    for minuto,valor in enumerate([23,24,25]):
        assert ingerir(db,ctx,valor,minuto).estado_calidad=='LECTURA_VALIDA'


@pytest.mark.parametrize('rol',['Productor','Ingeniero de Campo'])
def test_177_ingesta_fuera_de_rango_conserva_25_y_expone_condicion(cliente,db_session,contexto,rol):
    validas(db_session,contexto)
    assert ingerir(db_session,contexto,31,3).estado_calidad=='FUERA_DE_RANGO'
    # El trigger vigente conserva el evento nuevo en su caché; no se modifica telemetría.
    cache=db_session.execute(text('SELECT ultimo_valor,estado_calidad FROM modulo3.estados_actuales_sensores WHERE id_sensor=:s'),{'s':contexto['sensor']}).one()
    assert cache==(Decimal('31'),'FUERA_DE_RANGO')
    s=dashboard(cliente,contexto,rol)
    assert Decimal(s['ultimo_valor'])==25 and s['es_valor_operativo']
    assert s['estado_calidad']=='FUERA_DE_RANGO' and s['indicador_anomalia']
    assert s['estado_calidad_valor_operativo']=='LECTURA_VALIDA'
    assert datetime.fromisoformat(s['timestamp_estado_actual'])>datetime.fromisoformat(s['ultimo_timestamp_captura'])
    assert s['etiqueta_estado']=='Lectura fuera de rango'


@pytest.mark.parametrize('rol',['Productor','Ingeniero de Campo'])
def test_178_calibracion_ausente_no_oculta_condicion_ni_filtra_privacidad(cliente,db_session,contexto,rol):
    validas(db_session,contexto)
    # Preparación aislada: retirar exclusivamente la calibración sembrada para reproducir ausencia.
    db_session.execute(text('DELETE FROM modulo9.calibraciones WHERE id_sensor=:s'),{'s':contexto['sensor']})
    for minuto,valor in [(3,21.7),(4,22.3)]:
        assert ingerir(db_session,contexto,valor,minuto).estado_calidad=='ERROR_CALIBRACION'
    s=dashboard(cliente,contexto,rol)
    assert Decimal(s['ultimo_valor'])==25 and s['es_valor_operativo']
    assert s['indicador_anomalia'] and s['id_alerta'] is None
    if rol=='Productor':
        assert s['estado_calidad'] is None and s['etiqueta_estado']=='En revisión técnica'
        assert all(s[k] is None for k in ['nivel_bateria_pct','calidad_senal_rssi','calidad_senal_snr'])
    else:
        assert s['estado_calidad']=='ERROR_CALIBRACION' and s['etiqueta_estado']=='Requiere calibración'
        assert Decimal(s['nivel_bateria_pct'])==77 and Decimal(s['calidad_senal_rssi'])==-83


def test_168_recuperacion_y_llegada_tardia_no_sustituyen_referencia(cliente,db_session,contexto):
    validas(db_session,contexto)
    ingerir(db_session,contexto,31,3)
    ingerir(db_session,contexto,26,4)
    ingerir(db_session,contexto,40,-1)
    s=dashboard(cliente,contexto,'Productor')
    assert Decimal(s['ultimo_valor'])==26 and s['estado_calidad']=='LECTURA_VALIDA'
    assert not s['indicador_anomalia'] and s['es_valor_operativo']
    assert s['etiqueta_estado'] is None


def test_error_sin_referencia_no_inventa_lectura_operativa(cliente,db_session,contexto):
    assert ingerir(db_session,contexto,22,0).estado_calidad=='ERROR_CALIBRACION'
    for rol in ['Productor','Ingeniero de Campo']:
        s=dashboard(cliente,contexto,rol)
        assert s['ultimo_valor'] is None and not s['es_valor_operativo'] and s['indicador_anomalia']


def test_cache_anterior_y_aislamiento_por_finca(cliente,db_session,contexto):
    validas(db_session,contexto)
    ingerir(db_session,contexto,31,3)
    db_session.execute(text("UPDATE modulo3.estados_actuales_sensores SET ultimo_valor=25,estado_calidad='LECTURA_VALIDA' WHERE id_sensor=:s"),{'s':contexto['sensor']})
    assert dashboard(cliente,contexto,'Productor')['estado_calidad']=='FUERA_DE_RANGO'
    ajeno=h.hardware(db_session)
    ingerir(db_session,ajeno | {'base':contexto['base']},22,0)
    r=cliente.get('/iot/monitoreo/dashboard/'+str(ajeno['area']),headers=contexto['headers']['Productor'])
    assert r.status_code==200 and r.json()['sensores']==[] and r.json()['total']==0


def test_jwt_rbac_y_rol_postgresql(cliente,db_session,contexto):
    assert cliente.get('/iot/monitoreo/dashboard').status_code==401
    assert cliente.get('/iot/monitoreo/dashboard',headers=contexto['headers']['Contador']).status_code==403
    assert db_session.execute(text("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname='sgpmp_app'")).one()==(False,False)

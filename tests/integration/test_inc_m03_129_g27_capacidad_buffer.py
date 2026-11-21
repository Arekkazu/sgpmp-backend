# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-129-G27 RF-54/60/63: validar alertas 80/95, lectura por rol/finca, auditoría, rollback y concurrencia en PostgreSQL real. |
"""PostgreSQL real exclusivo: recepción del aviso y lectura por rol; no ejecuta firmware/MQTT."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
from threading import Barrier, Event

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from src.shared import database as modulo_db, jwt as jwt_module
from src.shared.database import get_db, get_db_sistema
from src.shared.error_handlers import register_error_handlers
from src.telemetry.application.use_cases.infraestructura.registrar_evento_buffer_use_case import RegistrarEventoBufferUseCase
from src.telemetry.infrastructure.adapters.dispositivo_m09_adapter import DispositivoM09Adapter
from src.telemetry.infrastructure.dto.evento_buffer_dto import RecibirEventoBufferDTO
from src.telemetry.infrastructure.repositories.alerta_repository import SqlAlchemyAlertaRepository
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import SqlAlchemyBitacoraAuditoriaIotRepository
from src.telemetry.infrastructure.routers import alerta_router
from src.telemetry.infrastructure.routers.infraestructura_iot_router import router

_spec = importlib.util.spec_from_file_location('inc684_base', Path(__file__).with_name('test_dev05_ingesta_bplus_postcommit.py'))
h = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h)
modelos, equipo = h.modelos, h.equipo
pytestmark = pytest.mark.integration


@pytest.fixture
def cliente(db_session, monkeypatch):
    monkeypatch.setattr(jwt_module, '_SECRET_KEY', 'sgpmp-integration-tests-only')
    monkeypatch.setattr(modulo_db, '_id_usuario_servicio', None)
    monkeypatch.setenv('BROKER_SERVICE_TOKEN', 'inc684-broker-local-only')
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    app.include_router(alerta_router.router)

    def rol_api(sesion, transaccion, conexion):
        conexion.exec_driver_sql('SET LOCAL ROLE sgpmp_app')

    def sesion(sistema=False):
        db_session.info.clear()
        event.listen(db_session, 'after_begin', rol_api)
        db_session.execute(text('SET LOCAL ROLE sgpmp_app'))
        assert db_session.execute(text('SELECT current_user')).scalar_one() == 'sgpmp_app'
        assert db_session.execute(text('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')).one() == (False, False)
        if sistema:
            modulo_db.declarar_identidad_sistema(db_session)
        try:
            yield db_session
        finally:
            event.remove(db_session, 'after_begin', rol_api)
            db_session.execute(text('RESET ROLE'))
            db_session.info.clear()

    def lectura():
        yield from sesion()

    def sistema():
        yield from sesion(True)

    app.dependency_overrides[get_db] = lectura
    app.dependency_overrides[get_db_sistema] = sistema
    with TestClient(app, raise_server_exceptions=False) as cliente:
        yield cliente



def datos(equipo, porcentaje=80, **cambios):
    return dict(dict(serial=equipo['serial'], evento='BUFFER_CAPACITY_WARNING',
        porcentaje_ocupacion=porcentaje, cantidad_datos_afectados=0,
        timestamp_evento=datetime.now(timezone.utc).isoformat()), **cambios)


def enviar(cliente, equipo, porcentaje=80, **cambios):
    r = cliente.post('/iot/eventos-buffer', json=datos(equipo, porcentaje, **cambios),
        headers={'Authorization': 'Bearer inc684-broker-local-only'})
    assert r.status_code == 201, r.text
    return r.json()


def alertas(db, equipo):
    return db.execute(text('''SELECT id_alerta,tipo_alerta::text,tipo_variable,severidad::text,
        estado_alerta::text,frecuencia_evento,ultima_ocurrencia,fecha_evento,metadato_evento
        FROM modulo3.alertas WHERE id_dispositivo_ioit=:d ORDER BY id_alerta'''),
        {'d': equipo['device']}).mappings().all()


def avisos_auditados(db, equipo):
    return db.execute(text("""SELECT accion_detallada,hash_integridad FROM modulo3.bitacora_auditoria_iot
        WHERE tipo_evento='BUFFER_CAPACITY_WARNING' AND entidad_afectada_id=:d
        ORDER BY fecha_hora,id_evento"""), {'d': str(equipo['device'])}).all()


@pytest.fixture
def auth(db_session, equipo, crear_usuario_db, crear_auth_headers):
    roles = dict(db_session.execute(text("SELECT nombre_rol,id_rol FROM modulo1.roles WHERE nombre_rol IN ('Administrador','Ingeniero de Campo','Productor')")).all())
    usuarios = {n: crear_usuario_db(id_rol=roles[r]) for n, r in
        [('admin', 'Administrador'), ('ingeniero', 'Ingeniero de Campo'), ('productor', 'Productor'), ('externo', 'Ingeniero de Campo')]}
    finca = db_session.execute(text('SELECT id_finca FROM modulo9.infraestructuras WHERE id_infraestructura=:a'), {'a': equipo['area']}).scalar_one()
    for nombre in ('ingeniero', 'productor'):
        db_session.execute(text('''INSERT INTO modulo9.usuarios_fincas(id_usuario_finca,id_usuario,id_finca,es_activo)
            SELECT COALESCE(max(id_usuario_finca),0)+1,:u,:f,true FROM modulo9.usuarios_fincas'''),
            {'u': usuarios[nombre]['id_usuario'], 'f': finca})
    db_session.commit()
    return {nombre: crear_auth_headers(usuario) for nombre, usuario in usuarios.items()}


@pytest.mark.parametrize('porcentaje,severidad', [(80, 'LEVE'), ('94.9999', 'LEVE'), (95, 'CRITICO'), (100, 'CRITICO')])
def test_aviso_persiste_alerta_historial_y_evidencia(cliente, db_session, equipo, porcentaje, severidad):
    r = enviar(cliente, equipo, porcentaje)
    fila, = alertas(db_session, equipo)
    assert (fila['id_alerta'], fila['tipo_alerta'], fila['tipo_variable'], fila['severidad'], fila['estado_alerta']) == (
        r['id_alerta'], 'TECNICA', 'BUFFER_CAPACITY_WARNING', severidad, 'ACTIVA')
    assert r['severidad'] == severidad and r['es_duplicado'] is False
    assert db_session.execute(text('SELECT count(*) FROM modulo3.historico_estados_alertas WHERE id_alerta=:a'), {'a': r['id_alerta']}).scalar_one() == 1
    evidencia, = avisos_auditados(db_session, equipo)
    assert evidencia[0]['porcentaje_ocupacion'] == str(porcentaje)
    assert evidencia[0]['severidad_alerta'] == severidad and len(evidencia[1]) == 64


def test_consolida_80_95_80_sin_rebajar_critico(cliente, db_session, equipo):
    resultados = [enviar(cliente, equipo, p) for p in (80, 95, 80)]
    assert len({r['id_alerta'] for r in resultados}) == 1
    assert [r['severidad'] for r in resultados] == ['LEVE', 'CRITICO', 'CRITICO']
    assert [r['es_duplicado'] for r in resultados] == [False, True, True]
    fila, = alertas(db_session, equipo)
    assert fila['severidad'] == 'CRITICO' and fila['frecuencia_evento'] == 3
    assert fila['metadato_evento']['porcentaje_ocupacion'] == '80'
    assert [e[0]['porcentaje_ocupacion'] for e in avisos_auditados(db_session, equipo)] == ['80', '95', '80']
    assert db_session.execute(text('SELECT count(*) FROM modulo3.historico_estados_alertas WHERE id_alerta=:a'), {'a': fila['id_alerta']}).scalar_one() == 1


def test_admin_ingeniero_ven_alerta_y_productor_no(cliente, db_session, equipo, auth):
    identificador = enviar(cliente, equipo, 95)['id_alerta']
    for nombre in ('admin', 'ingeniero'):
        r = cliente.get('/iot/alertas-tecnicas?severidad=CRITICO', headers=auth[nombre])
        assert r.status_code == 200, r.text
        fila, = [i for i in r.json()['items'] if i['id_alerta'] == identificador]
        assert fila['tipo_variable'] == 'BUFFER_CAPACITY_WARNING' and fila['severidad'] == 'CRITICO'
    assert cliente.get('/iot/alertas-tecnicas').status_code == 401
    assert cliente.get('/iot/alertas-tecnicas', headers=auth['productor']).status_code == 403
    fuera = cliente.get('/iot/alertas-tecnicas', headers=auth['externo'])
    assert fuera.status_code == 200 and fuera.json()['items'] == []
    operativas = cliente.get('/iot/alertas', headers=auth['productor'])
    assert operativas.status_code == 200, operativas.text
    assert identificador not in [i['id_alerta'] for i in operativas.json()['items']]


def test_en_atencion_escala_sin_modificar_estado_ni_historial(cliente, db_session, equipo, auth):
    identificador = enviar(cliente, equipo)['id_alerta']
    r = cliente.patch(f'/iot/alertas-tecnicas/{identificador}/estado', headers=auth['ingeniero'],
        json={'nuevo_estado': 'EN_ATENCION', 'motivo': 'Revisar capacidad del buffer'})
    assert r.status_code == 200, r.text
    assert enviar(cliente, equipo, 95)['id_alerta'] == identificador
    fila, = alertas(db_session, equipo)
    assert fila['severidad'] == 'CRITICO' and fila['estado_alerta'] == 'EN_ATENCION'
    assert db_session.execute(text('SELECT count(*) FROM modulo3.historico_estados_alertas WHERE id_alerta=:a'), {'a': identificador}).scalar_one() == 2


def test_incidente_cerrado_permite_otra_alerta(cliente, db_session, equipo, auth):
    primero = enviar(cliente, equipo)['id_alerta']
    r = cliente.patch(f'/iot/alertas-tecnicas/{primero}/estado', headers=auth['admin'],
        json={'nuevo_estado': 'DESCARTADA', 'motivo': 'Incidente revisado en pruebas'})
    assert r.status_code == 200, r.text
    nuevo = enviar(cliente, equipo, 95)
    assert nuevo['id_alerta'] != primero and nuevo['es_duplicado'] is False
    assert [a['estado_alerta'] for a in alertas(db_session, equipo)] == ['DESCARTADA', 'ACTIVA']


def test_reporte_anterior_no_retrocede_ocurrencia_y_conserva_contexto_inicial(cliente, db_session, equipo):
    actual = datetime.now(timezone.utc)
    enviar(cliente, equipo, 95, timestamp_evento=actual.isoformat())
    antes, = alertas(db_session, equipo)
    enviar(cliente, equipo, 80, timestamp_evento=(actual - timedelta(hours=1)).isoformat())
    despues, = alertas(db_session, equipo)
    assert despues['ultima_ocurrencia'] == actual and despues['severidad'] == 'CRITICO'
    assert despues['fecha_evento'] == antes['fecha_evento'] and despues['metadato_evento'] == antes['metadato_evento']


@pytest.mark.parametrize('cambio', [{'porcentaje_ocupacion': 101}, {'porcentaje_ocupacion': 'NaN'}, {'evento': 'NO_CATALOGADO'}])
def test_entrada_invalida_no_persiste(cliente, db_session, equipo, cambio):
    r = cliente.post('/iot/eventos-buffer', json=datos(equipo, **cambio),
        headers={'Authorization': 'Bearer inc684-broker-local-only'})
    assert r.status_code == 400, r.text
    assert not alertas(db_session, equipo) and not avisos_auditados(db_session, equipo)


@pytest.mark.parametrize('evento,severidad', [('BUFFER_OVERFLOW', 'MODERADO'), ('BUFFER_DATA_CORRUPTION', 'CRITICO')])
def test_compatibilidad_eventos_previos(cliente, db_session, equipo, evento, severidad):
    enviar(cliente, equipo)
    r = enviar(cliente, equipo, 100, evento=evento)
    assert r['tipo_alerta_tecnica'] == evento and r['severidad'] == severidad
    assert len(alertas(db_session, equipo)) == 2


@pytest.mark.parametrize('etapa', ['creacion', 'escalamiento'])
def test_fallo_evidencia_obligatoria_revierte_alerta_y_trigger(cliente, db_session, equipo, monkeypatch, etapa):
    antes = None
    if etapa == 'escalamiento':
        enviar(cliente, equipo)
        antes, = alertas(db_session, equipo)
    original = SqlAlchemyAlertaRepository._auditar
    def fallar(self, orm, tipo, detalle, usuario=None):
        if tipo == ('ALERTA_GENERADA' if etapa == 'creacion' else 'DUPLICADO_ALERTA_CORRELACIONADO'):
            raise RuntimeError('fallo controlado de evidencia obligatoria')
        return original(self, orm, tipo, detalle, usuario)
    monkeypatch.setattr(SqlAlchemyAlertaRepository, '_auditar', fallar)
    r = cliente.post('/iot/eventos-buffer', json=datos(equipo, 95),
        headers={'Authorization': 'Bearer inc684-broker-local-only'})
    assert r.status_code == 500, r.text
    assert r.json()['error_code'] == 'ERROR_INTERNO'
    if etapa == 'creacion':
        assert not alertas(db_session, equipo) and not avisos_auditados(db_session, equipo)
    else:
        despues, = alertas(db_session, equipo)
        assert despues == antes and len(avisos_auditados(db_session, equipo)) == 1


def test_auditoria_rf54_best_effort_no_revierte_alerta_confirmada(cliente, db_session, equipo, monkeypatch):
    original = SqlAlchemyBitacoraAuditoriaIotRepository.registrar
    def fallar(self, evento):
        if evento.tipo_evento == 'BUFFER_CAPACITY_WARNING':
            return evento
        return original(self, evento)
    monkeypatch.setattr(SqlAlchemyBitacoraAuditoriaIotRepository, 'registrar', fallar)
    r = enviar(cliente, equipo, 95)
    fila, = alertas(db_session, equipo)
    assert fila['id_alerta'] == r['id_alerta'] and fila['severidad'] == 'CRITICO'
    assert not avisos_auditados(db_session, equipo)


@pytest.mark.parametrize('existente', [False, True])
def test_avisos_concurrentes_comparten_alerta_y_maxima_severidad(integration_engine, monkeypatch, existente):
    monkeypatch.setattr(modulo_db, '_id_usuario_servicio', None)
    with Session(integration_engine) as db:
        equipo = h.hardware(db)
    motor = create_engine(integration_engine.url, use_insertmanyvalues=False, connect_args={'options': '-c role=sgpmp_app'})
    def ejecutar(db, porcentaje):
        modulo_db.declarar_identidad_sistema(db)
        assert db.execute(text('SELECT current_user')).scalar_one() == 'sgpmp_app'
        assert db.execute(text('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')).one() == (False, False)
        return RegistrarEventoBufferUseCase(db, DispositivoM09Adapter(db), SqlAlchemyAlertaRepository(db),
            SqlAlchemyBitacoraAuditoriaIotRepository(db)).execute(RecibirEventoBufferDTO(**datos(equipo, porcentaje)))
    try:
        with Session(motor) as bloqueo:
            if existente:
                ejecutar(bloqueo, 80)
            modulo_db.declarar_identidad_sistema(bloqueo)
            SqlAlchemyAlertaRepository(bloqueo).bloquear_dispositivo(equipo['device'])
            preparados = Barrier(3)
            termino = Event()
            def reportar(porcentaje):
                with Session(motor) as db:
                    preparados.wait(timeout=10)
                    resultado = ejecutar(db, porcentaje)
                    termino.set()
                    return resultado
            with ThreadPoolExecutor(max_workers=2) as pool:
                futuros = [pool.submit(reportar, p) for p in (80, 95)]
                try:
                    preparados.wait(timeout=10)
                    assert not termino.wait(.15)
                finally:
                    bloqueo.commit()
                resultados = [f.result(timeout=15) for f in futuros]
        assert len({r.id_alerta for r in resultados}) == 1
        with Session(integration_engine) as db:
            fila, = alertas(db, equipo)
            assert fila['severidad'] == 'CRITICO' and fila['frecuencia_evento'] == 2 + existente
    finally:
        motor.dispose()

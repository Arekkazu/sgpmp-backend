# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-47 RF-63: prueba persistencia triggers recuperacion y concurrencia |
# | 2026-10-25 | Arekkazu | INC-M03-135-G177 RF-63: verificar-integridad exige la ventana de fechas |
"""PostgreSQL real aislado. MQTT se representa por su función de persistencia."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import os
import subprocess
import sys
import uuid
import importlib
import importlib.util
from pathlib import Path
import pkgutil
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.telemetry.application.use_cases.auditoria.evidencia_iot import registrar_evidencia
from src.telemetry.application.use_cases.auditoria.verificar_integridad_bitacora_use_case import VerificarIntegridadBitacoraUseCase, hash_coincide
from src.telemetry.application.use_cases.inferencia.consolidar_paquete_inferencia_use_case import ConsolidarEnviarPaqueteUseCase
from src.telemetry.domain.entities.evento_auditoria_iot import ComponenteOrigen as C
from src.telemetry.domain.entities.alerta import Alerta
from src.telemetry.domain.entities.telemetria import EventoEdgeComputing
from src.telemetry.domain.repositories.postcommit_port import EtapaPostcommit
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import SqlAlchemyBitacoraAuditoriaIotRepository as Repo
from src.telemetry.infrastructure.repositories.alerta_repository import SqlAlchemyAlertaRepository
from src.telemetry.infrastructure.repositories.evento_edge_repository import SqlAlchemyEventoEdgeRepository
from src.telemetry.infrastructure.repositories.paquete_inferencia_repository import SqlAlchemyPaqueteInferenciaRepository
from src.telemetry.infrastructure.repositories.postcommit_repository import unidad_postcommit
from src.telemetry.infrastructure.workers.postcommit_worker import construir_procesador
from src.telemetry.infrastructure.adapters.motor_inferencia_stub_adapter import MotorInferenciaStubAdapter
from src.telemetry.infrastructure.adapters.aviso_integridad_m01_adapter import AvisoIntegridadM01Adapter

spec = importlib.util.spec_from_file_location('dev47_ingesta_datos', Path(__file__).with_name('test_dev05_ingesta_bplus_postcommit.py'))
h = importlib.util.module_from_spec(spec); spec.loader.exec_module(h)
pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def modelos():
    for paquete in ('src.configuration.infrastructure.models', 'src.biological_assets.infrastructure.models',
                    'src.telemetry.infrastructure.models', 'src.identity_access.infrastructure.models'):
        mod = importlib.import_module(paquete)
        for item in pkgutil.iter_modules(mod.__path__, paquete + '.'):
            importlib.import_module(item.name)


@pytest.fixture
def equipo(db_session):
    return h.hardware(db_session)


def eventos(db, tipo=None, dispositivo=None):
    lista = Repo(db).listar_todos_para_verificacion()
    return [e for e in lista if (tipo is None or e.tipo_evento == tipo) and (dispositivo is None or ((e.accion_detallada or {}).get('id_dispositivo_iot') == dispositivo or ((e.accion_detallada or {}).get('transicion') or {}).get('id_dispositivo_iot') == dispositivo))]


def etapa(db, nombre):
    procesador = construir_procesador(db.connection(), identidad=False)
    with unidad_postcommit(db.connection(), identidad=False) as unidad:
        ids = unidad.pendientes(nombre, 100, 1)
        for identificador in ids:
            if unidad.reclamar(nombre, identificador):
                procesador.acciones[nombre](unidad.db, identificador)
                unidad.registrar(nombre, identificador)
        unidad.confirmar()
    return ids


def test_ingesta_por_sql_mqtt_y_rechazo_de_unidad_dejan_resultado_idempotente(db_session, equipo):
    aceptada = h.sql_ingesta(db_session, equipo)
    rechazada = h.sql_ingesta(db_session, equipo, unidad='incompatible')
    assert aceptada.id_telemetria and rechazada.id_telemetria is None
    assert etapa(db_session, EtapaPostcommit.RF53_AUDITORIA)
    assert len(eventos(db_session, 'TELEMETRIA_VALIDADA', equipo['device'])) == 1
    assert eventos(db_session, 'TELEMETRIA_RECHAZADA', equipo['device'])
    assert not etapa(db_session, EtapaPostcommit.RF53_AUDITORIA)
    etapa(db_session, EtapaPostcommit.RF53_LECTURAS)
    assert len(eventos(db_session, 'TELEMETRIA_VALIDADA', equipo['device'])) == 1
    assert all(hash_coincide(e) for e in eventos(db_session))


def test_fuente_con_dispositivo_nulo_no_queda_bloqueada(db_session):
    db_session.execute(text("""INSERT INTO modulo3.bitacora_ingest
        (tipo_evento,estado_calidad,fecha_evento,payload_recibido)
        VALUES ('ERROR_PROCESAMIENTO','ERROR_AUTENTICACION',now(),'{"access_key":"no-copiar"}')"""))
    db_session.commit()
    etapa(db_session, EtapaPostcommit.RF53_AUDITORIA)
    resultado = eventos(db_session, 'ERROR_AUTENTICACION_DISPOSITIVO')
    assert len(resultado) == 1 and 'no-copiar' not in str(resultado[0].accion_detallada)


def test_lectura_confirmada_sin_consumir_bitacora_sql_recupera_auditoria(db_session, equipo):
    db_session.execute(text("""INSERT INTO modulo3.telemetrias(id_sensor,id_variable,id_dispositivo_iot,
        valor_crudo,valor_ajustado,timestamp_captura,timestamp_procesamiento,origen,estado_calidad,
        metadatos,categoria_variable,unidad_medida)
        VALUES (:s,9,:d,22,22,now()-interval '1 minute',now(),'TIEMPO_REAL','LECTURA_VALIDA',
                '{}','AMBIENTAL','°C')"""), {'s': equipo['sensor'], 'd': equipo['device']})
    db_session.commit()
    id_log = db_session.execute(text('SELECT id_bitacora_ingest FROM modulo3.bitacora_ingest WHERE id_dispositivo_iot=:d'), {'d': equipo['device']}).scalar_one()
    # El trigger ya genera la fuente SQL: la etapa de lecturas no depende de
    # que su proyección de resultados haya sido ejecutada.
    with unidad_postcommit(db_session.connection(), identidad=False) as unidad:
        assert id_log in unidad.pendientes(EtapaPostcommit.RF53_AUDITORIA, 100, 1)
    etapa(db_session, EtapaPostcommit.RF53_LECTURAS)
    assert len(eventos(db_session, 'TELEMETRIA_VALIDADA', equipo['device'])) == 1
    assert not etapa(db_session, EtapaPostcommit.RF53_LECTURAS)
    with unidad_postcommit(db_session.connection(), identidad=False) as unidad:
        assert id_log in unidad.pendientes(EtapaPostcommit.RF53_AUDITORIA, 100, 1)


def test_rf60_heartbeat_y_transicion_automatica_por_trigger(db_session, equipo):
    db_session.execute(text("""INSERT INTO modulo3.heartbeats(id_dispositivo_iot,tipo_mensaje,
        fecha_registro,fecha_recepcion,reloj_sincronizado,datos_pendientes_buffer)
        VALUES (:d,'HEARTBEAT',now(),now(),true,0)"""), {'d': equipo['device']})
    db_session.commit()
    etapa(db_session, EtapaPostcommit.HEARTBEAT_AUDITORIA)
    db_session.execute(text("UPDATE modulo3.estados_dispositivos_iot SET estado_actual='SIN_SEÑAL',causa_primaria='FALLO_CONECTIVIDAD' WHERE id_dispositivo_iot=:d"), {'d': equipo['device']})
    db_session.commit()
    etapa(db_session, EtapaPostcommit.RF60_TRANSICIONES)
    assert len(eventos(db_session, 'HEARTBEAT_RECIBIDO', equipo['device'])) == 1
    assert len(eventos(db_session, 'DISPOSITIVO_SIN_SEÑAL')) == 1
    assert not etapa(db_session, EtapaPostcommit.RF60_TRANSICIONES)
    # La reconexión activa dos escrituras históricas del SQL existente.
    db_session.execute(text("""INSERT INTO modulo3.heartbeats(id_dispositivo_iot,tipo_mensaje,
        fecha_registro,fecha_recepcion,reloj_sincronizado,datos_pendientes_buffer)
        VALUES (:d,'HEARTBEAT',now(),now(),true,0)"""), {'d': equipo['device']})
    db_session.commit()
    etapa(db_session, EtapaPostcommit.RF60_TRANSICIONES)
    assert len(eventos(db_session, 'DISPOSITIVO_RECONECTADO', equipo['device'])) == 1


def nueva_alerta(equipo):
    ahora = datetime.now(timezone.utc)
    return Alerta(tipo_alerta='TECNICA', severidad='LEVE', estado_alerta='ACTIVA',
        origen_evento='BACKEND', tipo_variable='BATERIA_BAJA', fecha_evento=ahora,
        fecha_generacion=ahora, id_dispositivo_ioit=equipo['device'], id_infraestructura=equipo['area'])


def test_alerta_creacion_transicion_y_consolidacion_atomicamente(db_session, equipo):
    repo = SqlAlchemyAlertaRepository(db_session)
    alerta = repo.guardar(nueva_alerta(equipo)); db_session.commit()
    repo.actualizar_deduplicacion(alerta.id_alerta, datetime.now(timezone.utc)); db_session.commit()
    repo.actualizar_estado(alerta.id_alerta, 'EN_ATENCION', None, None, datetime.now(timezone.utc)); db_session.commit()
    for tipo in ('ALERTA_GENERADA', 'ALERTA_RECONOCIDA', 'DUPLICADO_ALERTA_CORRELACIONADO'):
        assert len(eventos(db_session, tipo, equipo['device'])) == 1
    assert all(hash_coincide(e) for e in eventos(db_session))


def test_rollback_de_alerta_no_deja_evidencia_huerfana(db_session, equipo):
    # SAVEPOINT: ambos efectos se revierten juntos aunque el registro sea append-only.
    with db_session.begin_nested() as transaccion:
        alerta = SqlAlchemyAlertaRepository(db_session).guardar(nueva_alerta(equipo))
        assert eventos(db_session, 'ALERTA_GENERADA', equipo['device'])
        transaccion.rollback()
    assert not eventos(db_session, 'ALERTA_GENERADA', equipo['device'])
    assert db_session.execute(text('SELECT count(*) FROM modulo3.alertas WHERE id_alerta=:id'), {'id': alerta.id_alerta}).scalar_one() == 0


@pytest.mark.parametrize('motor,estado,tipo', [('stub', 'PENDIENTE', None),
    ('positivo', 'ENVIADO', 'PAQUETE_ENVIADO_IA'), ('negativo', 'FALLIDO', 'FALLO_ENVIO_PAQUETE')])
def test_paquete_y_resultado_real_del_adaptador(db_session, equipo, motor, estado, tipo):
    ahora = datetime.now(timezone.utc)
    edge = SqlAlchemyEventoEdgeRepository(db_session).guardar(EventoEdgeComputing(
        id_dispositivo_iot=equipo['device'], id_sensor=equipo['sensor'],
        clasificacion_rf55='DESVIACION_SIMPLE', tipo_evento='ALERTA_GENERADA',
        fecha_captura=ahora, fecha_procesamiento=ahora, origen_dato='TIEMPO_REAL',
        estado_conectividad=True, severidad='LEVE',
        variables_involucradas=[{'tipo_variable': 'TEMPERATURA_AMBIENTAL', 'valor': '22', 'unidad': '°C'}]))
    db_session.commit()
    puerto = MotorInferenciaStubAdapter() if motor == 'stub' else Mock()
    if motor != 'stub': puerto.enviar_paquete.return_value = motor == 'positivo'
    caso = ConsolidarEnviarPaqueteUseCase(db_session, SqlAlchemyPaqueteInferenciaRepository(db_session), puerto)
    paquete = caso.execute(edge)
    assert paquete.estado_paquete == estado
    assert len(eventos(db_session, 'PAQUETE_INFERENCIA_GENERADO', equipo['device'])) == 1
    if tipo: assert len(eventos(db_session, tipo, equipo['device'])) == 1
    else: assert not eventos(db_session, 'PAQUETE_ENVIADO_IA', equipo['device']) and paquete.intento_envios == 0
    assert caso.execute(edge).id_paquetes_inferencia == paquete.id_paquetes_inferencia
    assert len(eventos(db_session, 'PAQUETE_INFERENCIA_GENERADO', equipo['device'])) == 1


def test_e6_hash_invalido_marca_externa_y_sin_recursion(db_session):
    original = registrar_evidencia(Repo(db_session), 'TELEMETRIA_VALIDADA', C.RF53)
    # Copia deliberadamente inconsistente: no se desactiva DB-11 para alterar una fila.
    original.hash_integridad = '0' * 64
    copia = Repo(db_session).registrar(original); db_session.commit()
    caso = VerificarIntegridadBitacoraUseCase(db_session, Repo(db_session), AvisoIntegridadM01Adapter(db_session))
    r = caso.execute(); segundo = caso.execute()
    assert r.ids_comprometidos == [str(copia.id_evento)]
    assert r.incidentes_creados == 1 and segundo.incidentes_creados == 0
    assert r.notificaciones_pendientes == 1
    incidente = eventos(db_session, 'INTEGRIDAD_COMPROMETIDA')[0]
    assert incidente.severidad_log == 'CRITICAL' and hash_coincide(incidente)
    assert Repo(db_session).obtener(copia.id_evento).hash_integridad == '0' * 64
    assert Repo(db_session).obtener(copia.id_evento).integridad_comprometida


@pytest.mark.parametrize('tabla', ['bitacora_auditoria_iot', 'bitacora_ingest'])
@pytest.mark.parametrize('operacion', ['UPDATE', 'DELETE'])
def test_db11_rechaza_cambios_a_bitacoras(db_session, tabla, operacion):
    if tabla == 'bitacora_auditoria_iot':
        registrar_evidencia(Repo(db_session), 'TELEMETRIA_VALIDADA', C.RF53)
        asignacion = "descripcion='alterado'"
    else:
        db_session.execute(text("INSERT INTO modulo3.bitacora_ingest(fecha_evento) VALUES(now())"))
        asignacion = "descripcion_text='alterado'"
    db_session.commit()
    with pytest.raises(Exception, match='Append-Only'):
        with db_session.begin_nested():
            consulta = f'UPDATE modulo3.{tabla} SET {asignacion}' if operacion == 'UPDATE' else f'DELETE FROM modulo3.{tabla}'
            db_session.execute(text(consulta))


@pytest.mark.parametrize('ruta', ['/iot/telemetria', '/iot/telemetria/batch'])
def test_estructura_http_bitacora_independiente_y_sin_secretos(db_session, headers_broker, monkeypatch, ruta):
    from src.shared.database import get_db_sistema
    from src.shared.error_handlers import register_error_handlers
    from src.telemetry.infrastructure.routers.telemetria_router import router
    from src.telemetry.infrastructure.routers import ruta_ingesta_auditada
    from src.shared.database import declarar_identidad_sistema
    def sesion():
        nueva = Session(bind=db_session.connection(), join_transaction_mode='create_savepoint')
        declarar_identidad_sistema(nueva)
        return nueva
    monkeypatch.setattr(ruta_ingesta_auditada, 'sesion_sistema', sesion)
    app = FastAPI(); register_error_handlers(app); app.include_router(router)
    app.dependency_overrides[get_db_sistema] = lambda: db_session
    previos = {e.id_evento for e in eventos(db_session, 'ERROR_ESTRUCTURA_MENSAJE')}
    lecturas_antes = db_session.execute(text('SELECT count(*) FROM modulo3.telemetrias')).scalar_one()
    with TestClient(app, headers=headers_broker) as client:
        r = client.post(ruta, json={'access_key': 'secreto-no-auditar'})
    assert r.status_code == 400
    evidencia = [e for e in eventos(db_session, 'ERROR_ESTRUCTURA_MENSAJE') if e.id_evento not in previos]
    assert len(evidencia) == 1 and 'secreto-no-auditar' not in str(evidencia[0].accion_detallada)
    assert db_session.execute(text('SELECT count(*) FROM modulo3.telemetrias')).scalar_one() == lecturas_antes


@pytest.fixture(scope='module')
def motor_exclusivo(integration_engine):
    url = integration_engine.url
    if url.host not in ('127.0.0.1', 'localhost', '::1'):
        pytest.skip('Los commits reales de esta prueba requieren PostgreSQL local aislado.')
    nombre = 'dev47_test_' + uuid.uuid4().hex
    admin = create_engine(url.set(database='postgres'), isolation_level='AUTOCOMMIT')
    motor = None
    with admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{nombre}"'))
    try:
        nueva = url.set(database=nombre).render_as_string(hide_password=False)
        entorno = os.environ | {'DATABASE_URL': nueva, 'ALEMBIC_DATABASE_URL': nueva}
        r = subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], env=entorno,
                           capture_output=True, text=True, timeout=180)
        assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
        motor = create_engine(nueva, use_insertmanyvalues=False)
        yield motor
    finally:
        if motor is not None: motor.dispose()
        with admin.connect() as c:
            c.execute(text(f'DROP DATABASE "{nombre}" WITH (FORCE)'))
        admin.dispose()


def test_e6_verificadores_concurrentes_un_incidente_y_un_aviso(motor_exclusivo):
    motor = motor_exclusivo
    with Session(motor) as db:
        fuente = registrar_evidencia(Repo(db), 'TELEMETRIA_VALIDADA', C.RF53)
        fuente.hash_integridad = '0' * 64
        copia = Repo(db).registrar(fuente); identificador = str(copia.id_evento)
        db.commit()

    class AvisoTransaccional:
        # Doble del puerto: solo acredita el marcador RF-63, no entrega real RF-14.
        def notificar(self, *args): return 1

    def verificar():
        with Session(motor) as db:
            return VerificarIntegridadBitacoraUseCase(db, Repo(db), AvisoTransaccional()).execute()
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(lambda _: verificar(), range(2)))
    assert sum(r.incidentes_creados for r in resultados) == 1
    with Session(motor) as db:
        assert db.execute(text("""SELECT count(*) FROM modulo3.bitacora_auditoria_iot
            WHERE accion_detallada->'compromiso'->>'id_evento'=:id"""), {'id': identificador}).scalar_one() == 1
        assert db.execute(text("""SELECT count(*) FROM modulo3.bitacora_auditoria_iot
            WHERE accion_detallada ? 'aviso_incidente'""")).scalar_one() == 1


def test_postcommit_fallido_conserva_fuente_y_recupera_una_vez(motor_exclusivo, monkeypatch):
    motor = motor_exclusivo
    with Session(motor) as db:
        equipo = h.hardware(db)
        lectura = h.sql_ingesta(db, equipo)
    original = Repo.registrar
    def fallo(self, evento):
        return evento if evento.tipo_evento == 'TELEMETRIA_VALIDADA' else original(self, evento)
    monkeypatch.setattr(Repo, 'registrar', fallo)
    etapa_rf53 = EtapaPostcommit.RF53_AUDITORIA
    acciones = construir_procesador(motor, identidad=False).acciones
    with pytest.raises(RuntimeError, match='evidencia obligatoria'):
        with unidad_postcommit(motor, identidad=False) as unidad:
            identificador = unidad.pendientes(etapa_rf53, 10, 1)[0]
            assert unidad.reclamar(etapa_rf53, identificador)
            acciones[etapa_rf53](unidad.db, identificador)
            unidad.registrar(etapa_rf53, identificador)
            unidad.confirmar()
    monkeypatch.setattr(Repo, 'registrar', original)
    with Session(motor) as db:
        assert db.execute(text('SELECT count(*) FROM modulo3.telemetrias WHERE id_telemetria=:id'), {'id': lectura.id_telemetria}).scalar_one() == 1
    def procesar():
        with unidad_postcommit(motor, identidad=False) as unidad:
            ids = unidad.pendientes(etapa_rf53, 100, 1)
            for identificador in ids:
                if unidad.reclamar(etapa_rf53, identificador):
                    acciones[etapa_rf53](unidad.db, identificador)
                    unidad.registrar(etapa_rf53, identificador)
            unidad.confirmar()
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: procesar(), range(2)))
    with Session(motor) as db:
        assert len([e for e in eventos(db, 'TELEMETRIA_VALIDADA') if e.entidad_afectada_id == str(lectura.id_telemetria)]) == 1


def test_get_integridad_autorizado_no_cae_en_ruta_uuid(db_session, monkeypatch):
    from types import SimpleNamespace
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers
    from src.shared import rbac
    from src.identity_access.infrastructure.dependencies import get_current_user
    from src.telemetry.infrastructure.routers.auditoria_iot_router import router
    app = FastAPI(); register_error_handlers(app); app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id_estado_cuenta=2, id_rol=99)
    monkeypatch.setattr(rbac, 'tiene_permiso', lambda *a, **k: True)
    with TestClient(app) as client:
        # INC-M03-135-G177: la ventana es obligatoria; sin ella responde 400.
        assert client.get('/iot/auditoria/verificar-integridad').status_code == 400
        respuesta = client.get('/iot/auditoria/verificar-integridad', params={
            'fecha_desde': '2026-01-01T00:00:00Z', 'fecha_hasta': '2026-01-02T00:00:00Z'})
    assert respuesta.status_code == 200 and respuesta.json()['comprometidos'] == 0


def test_batch_http_audita_cada_resultado_confirmado(db_session, equipo, headers_broker):
    from src.shared.database import get_db_sistema
    from src.shared.error_handlers import register_error_handlers
    from src.telemetry.infrastructure.routers.telemetria_router import router
    app = FastAPI(); register_error_handlers(app); app.include_router(router)
    app.dependency_overrides[get_db_sistema] = lambda: db_session
    primero = h.payload(equipo, origen='BUFFER_LOCAL')
    segundo = h.payload(equipo, origen='BUFFER_LOCAL', unidad='incompatible',
        timestamp_captura=(datetime.now(timezone.utc)-timedelta(minutes=2)).isoformat())
    with TestClient(app, headers=headers_broker) as client:
        respuesta = client.post('/iot/telemetria/batch', json={'registros': [primero, segundo]})
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()['aceptados'] == respuesta.json()['rechazados'] == 1
    etapa(db_session, EtapaPostcommit.RF53_AUDITORIA)
    assert len(eventos(db_session, 'TELEMETRIA_VALIDADA', equipo['device'])) == 1
    assert len(eventos(db_session, 'TELEMETRIA_RECHAZADA', equipo['device'])) == 1


def test_fallo_auditoria_alerta_impide_confirmar_negocio(db_session, equipo, monkeypatch):
    monkeypatch.setattr(Repo, 'registrar', lambda self, e: e)
    from src.shared.errors import InfrastructureError
    with pytest.raises(InfrastructureError) as error:
        with db_session.begin_nested():
            SqlAlchemyAlertaRepository(db_session).guardar(nueva_alerta(equipo))
    assert isinstance(error.value.original_error, RuntimeError)
    assert db_session.execute(text('SELECT count(*) FROM modulo3.alertas WHERE id_dispositivo_ioit=:d'), {'d': equipo['device']}).scalar_one() == 0

# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-29 RF-56: casos de dispositivo y sensor inactivos (401) |
# | 2026-10-21 | Arekkazu | DEV-45 RF-56: E1 bitácora de rechazos, E3 evento individual, E6 límite por dispositivo, E7 intento no autorizado |
"""RF-56 DEV-17: router, adaptadores y PostgreSQL reales, sin motor IA real."""
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import importlib
import pkgutil
import uuid
from threading import Barrier
from time import sleep
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.database import get_db_sistema
from src.shared.error_handlers import register_error_handlers
from src.telemetry.application.use_cases.inferencia.consolidar_paquete_inferencia_use_case import ConsolidarEnviarPaqueteUseCase
from src.telemetry.domain.entities.telemetria import EventoEdgeComputing
from src.telemetry.domain.repositories.motor_inferencia_port import MotorInferenciaPort
from src.telemetry.infrastructure.adapters.motor_inferencia_stub_adapter import MotorInferenciaStubAdapter
from src.telemetry.infrastructure.models.evento_edge_model import EventoEdgeComputingModel
from src.telemetry.infrastructure.repositories.evento_edge_repository import SqlAlchemyEventoEdgeRepository
from src.telemetry.infrastructure.repositories.paquete_inferencia_repository import SqlAlchemyPaqueteInferenciaRepository
from src.telemetry.infrastructure.routers import evento_edge_router

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def modelos():
    for paquete in ("src.configuration.infrastructure.models", "src.biological_assets.infrastructure.models", "src.telemetry.infrastructure.models", "src.identity_access.infrastructure.models"):
        mod = importlib.import_module(paquete)
        for item in pkgutil.iter_modules(mod.__path__, paquete + "."):
            importlib.import_module(item.name)


def _crear_hardware(db_session):
    tag = uuid.uuid4().hex[:12]
    nombre = 'Dev Pendiente ' + ''.join(chr(97 + int(c,16)) for c in tag)
    area = db_session.execute(text("""
        WITH finca AS (
          INSERT INTO modulo9.fincas(nombre,ubicacion,tamano_h,es_activo,fecha_creacion,fecha_actualizacion)
          VALUES (:nombre,'{}',10,true,now(),now()) RETURNING id_finca)
        INSERT INTO modulo9.infraestructuras(nombre,id_finca,superficie,es_activo,tipo)
        SELECT :nombre,id_finca,100,true,'Estanque' FROM finca RETURNING id_infraestructura
    """), {"nombre": nombre}).scalar_one()
    device = db_session.execute(text("""
        INSERT INTO modulo9.dispositivos_iot(serial,descripcion,es_activo,fecha_creacion,id_infraestructura,id_tipo_dispositivo)
        VALUES (:serial,'DEV-17',true,now(),:area,3) RETURNING id_dispositivo_iot
    """), {"serial": tag, "area": area}).scalar_one()
    sensor = db_session.execute(text("""
        INSERT INTO modulo9.sensores(id_dispositivo_iot,es_activo,nombre)
        VALUES (:device,true,'Temperatura Dev Pendiente') RETURNING id_sensores
    """), {"device": device}).scalar_one()
    db_session.commit()
    return {"device": device, "sensor": sensor, "serial": tag, "area": area}


@pytest.fixture
def hardware(db_session):
    return _crear_hardware(db_session)


@pytest.fixture
def client(db_session, headers_broker):
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(evento_edge_router.router)
    app.dependency_overrides[get_db_sistema] = lambda: db_session
    with TestClient(app, raise_server_exceptions=False, headers=headers_broker) as test_client:
        yield test_client


def _payload(hardware, clasificacion='DESVIACION_SIMPLE'):
    ts = datetime.now(timezone.utc) - timedelta(minutes=1)
    return dict(device_id=hardware['device'], sensor_id=hardware['sensor'], serial=hardware['serial'],
                clasificacion_rf55=clasificacion, severidad='MODERADO', origen='TIEMPO_REAL',
                timestamp_captura=ts.isoformat(), timestamp_procesamiento_edge=ts.isoformat(),
                estado_conectividad=True, metadata_edge={'origen_prueba':'DEV-17'},
                variables_involucradas=[
                    {'tipo_variable':'TEMPERATURA_AMBIENTAL','valor':'38.5000','unidad':'°C','timestamp_captura':ts.isoformat()},
                    {'tipo_variable':'HUMEDAD_RELATIVA','valor':'90.0000','unidad':'%','timestamp_captura':ts.isoformat()},
                ])


def _paquetes(db, device):
    return db.execute(text('SELECT * FROM modulo3.paquetes_inferencia WHERE id_dispositivo_iot=:d ORDER BY id_paquetes_inferencia'), {'d':device}).mappings().all()


def _evento(db, id_evento):
    return SqlAlchemyEventoEdgeRepository._a_entidad(db.get(EventoEdgeComputingModel, id_evento))


@pytest.mark.parametrize('clasificacion', ['DESVIACION_SIMPLE','DESVIACION_COMPUESTA'])
def test_evento_edge_a_paquete_pendiente_persistido_y_recuperable(client, db_session, hardware, clasificacion):
    payload = _payload(hardware, clasificacion)
    response = client.post('/iot/eventos-edge', json=payload, headers={'X-Gateway-Id':'dev17-test'})
    assert response.status_code == 201, response.text
    assert response.json()['paquete_inferencia_estado'] == 'PENDIENTE'
    db_session.rollback()  # Un rollback posterior no debe eliminar el paquete confirmado.
    rows = _paquetes(db_session, hardware['device'])
    assert len(rows) == 1
    row = rows[0]
    assert row['estado_paquete'] == 'PENDIENTE' and row['intento_envios'] == 0
    assert row['id_evento_edge_computing'] == response.json()['id_evento_edge_computing']
    assert row['id_sensor'] == hardware['sensor']
    assert row['valor_numerico'] == Decimal('38.5000')
    assert row['estado_desviacion'] == clasificacion and row['severidad'] == 'MODERADO'
    assert row['contexto_incomplento'] is False
    assert {v['tipo_variable'] for v in row['contexto_ambiental']['AMBIENTAL']} == {'TEMPERATURA_AMBIENTAL','HUMEDAD_RELATIVA'}
    assert row['metadatos']['clasificacion_rf55'] == clasificacion
    assert datetime.fromisoformat(row['metadatos']['timestamp_captura']) == datetime.fromisoformat(payload['timestamp_captura'])
    with Session(bind=db_session.get_bind(), join_transaction_mode='create_savepoint') as lectura:
        recuperado = SqlAlchemyPaqueteInferenciaRepository(lectura).obtener_por_evento(row['id_evento_edge_computing'])
        assert recuperado.id_paquetes_inferencia == row['id_paquetes_inferencia']
        assert recuperado.estado_paquete == 'PENDIENTE' and recuperado.intento_envios == 0
    evento = db_session.execute(text('SELECT enviado_backend,metadatos FROM modulo3.eventos_edge_computing WHERE id_evento_edge_computing=:id'), {'id':row['id_evento_edge_computing']}).one()
    assert evento[0] is False
    assert evento[1]['origen_prueba'] == 'DEV-17'


@pytest.mark.parametrize('clasificacion', ['NORMAL','ERROR_CONFIGURACION'])
def test_eventos_sin_envio_conservan_flujo_actual(client, db_session, hardware, clasificacion):
    response = client.post('/iot/eventos-edge', json=_payload(hardware, clasificacion))
    assert response.status_code == 201, response.text
    assert response.json()['paquete_inferencia_estado'] is None
    assert _paquetes(db_session, hardware['device']) == []


@pytest.mark.parametrize('resultado,estado', [(True,'ENVIADO'), (False,'FALLIDO'), (RuntimeError('sin conexion'),'FALLIDO')])
def test_doble_de_motor_conserva_confirmacion_y_fallo(client, db_session, hardware, monkeypatch, resultado, estado):
    motor = Mock(spec=MotorInferenciaPort)
    def enviar(paquete):
        # La persistencia precede cualquier comunicación externa.
        assert _paquetes(db_session, hardware['device'])[0]['estado_paquete'] == 'PENDIENTE'
        if isinstance(resultado, Exception):
            raise resultado
        return resultado
    motor.enviar_paquete.side_effect = enviar
    monkeypatch.setattr(evento_edge_router, 'MotorInferenciaStubAdapter', lambda: motor)
    response = client.post('/iot/eventos-edge', json=_payload(hardware))
    assert response.status_code == 201, response.text
    assert response.json()['paquete_inferencia_estado'] == estado
    row = _paquetes(db_session, hardware['device'])[0]
    assert row['estado_paquete'] == estado and row['intento_envios'] == 1
    motor.enviar_paquete.assert_called_once()


@pytest.mark.parametrize('fase', ['guardar','commit'])
def test_fallo_persistencia_no_confirma_ni_invoca_motor(client, db_session, hardware, monkeypatch, fase):
    motor = Mock(spec=MotorInferenciaPort)
    monkeypatch.setattr(evento_edge_router, 'MotorInferenciaStubAdapter', lambda: motor)
    if fase == 'guardar':
        guardar = SqlAlchemyPaqueteInferenciaRepository.guardar
        def fallar(self, paquete):
            guardar(self, paquete)
            self.db.execute(text('SELECT 1 / 0'))
        monkeypatch.setattr(SqlAlchemyPaqueteInferenciaRepository, 'guardar', fallar)
    else:
        commit = db_session.commit
        intentos = 0
        def fallar():
            nonlocal intentos
            intentos += 1
            if intentos == 2:
                raise RuntimeError('commit no disponible')
            commit()
        monkeypatch.setattr(db_session, 'commit', fallar)
    response = client.post('/iot/eventos-edge', json=_payload(hardware))
    assert response.status_code == 500, response.text
    motor.enviar_paquete.assert_not_called()
    assert _paquetes(db_session, hardware['device']) == []
    # La transacción anterior conservó el evento; el request no confirma éxito.
    assert db_session.execute(text('SELECT count(*) FROM modulo3.eventos_edge_computing WHERE id_dispositivo_iot=:d'), {'d':hardware['device']}).scalar_one() == 1


def test_reconsolidar_mismo_evento_reutiliza_un_solo_paquete(client, db_session, hardware):
    response = client.post('/iot/eventos-edge', json=_payload(hardware))
    assert response.status_code == 201, response.text
    id_evento = response.json()['id_evento_edge_computing']
    previo = _paquetes(db_session, hardware['device'])[0]
    motor = Mock(spec=MotorInferenciaPort)
    uc = ConsolidarEnviarPaqueteUseCase(db_session, SqlAlchemyPaqueteInferenciaRepository(db_session), motor)
    for _ in range(2):
        paquete = uc.execute(_evento(db_session, id_evento))
        assert paquete.id_paquetes_inferencia == previo['id_paquetes_inferencia']
    assert len(_paquetes(db_session, hardware['device'])) == 1
    motor.enviar_paquete.assert_not_called()


def test_fallo_estado_conserva_paquete_y_reconsolidacion_no_reenvia(client, db_session, hardware, monkeypatch):
    motor = Mock(spec=MotorInferenciaPort)
    motor.enviar_paquete.return_value = True
    monkeypatch.setattr(evento_edge_router, 'MotorInferenciaStubAdapter', lambda: motor)
    actualizar = SqlAlchemyPaqueteInferenciaRepository.actualizar_estado
    def fallar(self, *args):
        actualizar(self, *args)
        self.db.execute(text('SELECT 1 / 0'))
    monkeypatch.setattr(SqlAlchemyPaqueteInferenciaRepository, 'actualizar_estado', fallar)
    response = client.post('/iot/eventos-edge', json=_payload(hardware))
    assert response.status_code == 500, response.text
    row = _paquetes(db_session, hardware['device'])[0]
    assert row['estado_paquete'] == 'PENDIENTE' and row['intento_envios'] == 0
    uc = ConsolidarEnviarPaqueteUseCase(db_session, SqlAlchemyPaqueteInferenciaRepository(db_session), motor)
    recuperado = uc.execute(_evento(db_session, row['id_evento_edge_computing']))
    assert recuperado.id_paquetes_inferencia == row['id_paquetes_inferencia']
    motor.enviar_paquete.assert_called_once()


@pytest.mark.parametrize('invalidez,http', [('clave',401),('sensor',401),('estructura',400),('futuro',400),
                                             ('dispositivo_inactivo',401),('sensor_inactivo',401)])
def test_recepcion_conserva_validaciones_existentes(client, db_session, hardware, invalidez, http):
    payload = _payload(hardware)
    if invalidez == 'dispositivo_inactivo':
        db_session.execute(text('UPDATE modulo9.dispositivos_iot SET es_activo=false WHERE id_dispositivo_iot=:id'), {'id':hardware['device']})
        db_session.commit()
    elif invalidez == 'sensor_inactivo':
        db_session.execute(text('UPDATE modulo9.sensores SET es_activo=false WHERE id_sensores=:id'), {'id':hardware['sensor']})
        db_session.commit()
    elif invalidez == 'clave':
        payload['serial'] = 'serial-ajeno-prueba'
    elif invalidez == 'sensor':
        payload['sensor_id'] = 2147483000
    elif invalidez == 'estructura':
        payload.pop('device_id')
    else:
        payload['timestamp_captura'] = (datetime.now(timezone.utc)+timedelta(minutes=2)).isoformat()
    response = client.post('/iot/eventos-edge', json=payload)
    assert response.status_code == http, response.text
    assert _paquetes(db_session, hardware['device']) == []
    assert db_session.execute(text('SELECT count(*) FROM modulo3.eventos_edge_computing WHERE id_dispositivo_iot=:d'), {'d':hardware['device']}).scalar_one() == 0


def test_consolidaciones_concurrentes_del_mismo_evento_no_duplican(integration_engine):
    # Dos conexiones deben ver el padre: este fixture se confirma únicamente
    # en TEST. M09 prohíbe borrar dispositivos; se inactiva el hardware propio
    # al terminar. Por ello esta prueba requiere una base de integración aislada.
    with Session(integration_engine) as seed:
        hw = _crear_hardware(seed)
        payload = _payload(hw)
        evento = SqlAlchemyEventoEdgeRepository(seed).guardar(EventoEdgeComputing(
            id_dispositivo_iot=hw['device'], id_sensor=hw['sensor'],
            clasificacion_rf55='DESVIACION_SIMPLE', tipo_evento='ALERTA_GENERADA',
            severidad='MODERADO', fecha_captura=datetime.fromisoformat(payload['timestamp_captura']),
            fecha_procesamiento=datetime.fromisoformat(payload['timestamp_procesamiento_edge']),
            origen_dato='TIEMPO_REAL', estado_conectividad=True,
            variables_involucradas=payload['variables_involucradas'],
        ))
        id_evento = evento.id_evento_edge_computing
        finca = seed.execute(text('SELECT id_finca FROM modulo9.infraestructuras WHERE id_infraestructura=:a'), {'a':hw['area']}).scalar_one()
        seed.commit()
    barrera = Barrier(2)

    class RepositorioConcurrente(SqlAlchemyPaqueteInferenciaRepository):
        def obtener_por_evento(self, *args, **kwargs):
            barrera.wait(timeout=5)
            return super().obtener_por_evento(*args, **kwargs)

        def guardar(self, paquete):
            # Amplía la ventana entre lectura sin paquete y creación para
            # reproducir la carrera; la exclusión la realiza PostgreSQL.
            sleep(0.1)
            return super().guardar(paquete)

    def consolidar():
        with Session(integration_engine) as db:
            db.execute(text("SET LOCAL lock_timeout = '5s'"))
            uc = ConsolidarEnviarPaqueteUseCase(db, RepositorioConcurrente(db), MotorInferenciaStubAdapter())
            paquete = uc.execute(_evento(db, id_evento))
            return paquete.id_paquetes_inferencia, paquete.estado_paquete, paquete.intento_envios

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(consolidar) for _ in range(2)]
            resultados = [f.result(timeout=10) for f in futures]
        assert resultados[0] == resultados[1]
        assert resultados[0][1:] == ('PENDIENTE',0)
        with Session(integration_engine) as lectura:
            assert len(_paquetes(lectura, hw['device'])) == 1
    finally:
        with integration_engine.begin() as conn:
            conn.execute(text('DELETE FROM modulo3.paquetes_inferencia WHERE id_evento_edge_computing=:id'), {'id':id_evento})
            conn.execute(text('DELETE FROM modulo3.eventos_edge_computing WHERE id_evento_edge_computing=:id'), {'id':id_evento})
            conn.execute(text('UPDATE modulo9.sensores SET es_activo=false WHERE id_sensores=:id'), {'id':hw['sensor']})
            conn.execute(text('UPDATE modulo9.dispositivos_iot SET es_activo=false WHERE id_dispositivo_iot=:id'), {'id':hw['device']})
            conn.execute(text('UPDATE modulo9.infraestructuras SET es_activo=false WHERE id_infraestructura=:id'), {'id':hw['area']})
            conn.execute(text('UPDATE modulo9.fincas SET es_activo=false WHERE id_finca=:id'), {'id':finca})


# ── DEV-45 (RF-56 G-13): E1, E3, E6, E7 ─────────────────────────────────────

def _bitacora(db, tipo, entidad):
    # id_evento es UUID: se filtra por la entidad, no se ordena por id.
    return db.execute(text(
        "SELECT accion_detallada FROM modulo3.bitacora_auditoria_iot "
        "WHERE tipo_evento = :t AND entidad_afectada_id = :e ORDER BY fecha_hora DESC"),
        {'t': tipo, 'e': entidad}).scalars().all()


@pytest.mark.parametrize('invalidez,codigo', [('estructura', 'ERROR_ESTRUCTURA'), ('futuro', 'TIMESTAMP_FUTURO')])
def test_e1_el_evento_rechazado_queda_en_bitacora_con_su_contenido(client, db_session, hardware, invalidez, codigo):
    payload = _payload(hardware)
    if invalidez == 'estructura':
        payload.pop('device_id')
    else:
        payload['timestamp_captura'] = (datetime.now(timezone.utc)+timedelta(minutes=2)).isoformat()
    assert client.post('/iot/eventos-edge', json=payload).status_code == 400
    detalle = _bitacora(db_session, 'EVENTO_EDGE_RECHAZADO', hardware['serial'])[0]
    assert detalle['codigo_error'] == codigo
    assert detalle['evento']['metadata_edge'] == {'origen_prueba': 'DEV-17'}


def test_e3_timestamps_dispersos_se_procesan_como_evento_individual(client, db_session, hardware):
    payload = _payload(hardware)
    payload['variables_involucradas'][1]['timestamp_captura'] = (
        datetime.now(timezone.utc) - timedelta(minutes=1, seconds=30)).isoformat()
    response = client.post('/iot/eventos-edge', json=payload)
    assert response.status_code == 201, response.text
    row = _paquetes(db_session, hardware['device'])[0]
    assert row['contexto_incomplento'] is True  # nombre real de la columna
    assert list(row['contexto_ambiental']) == ['AMBIENTAL'] and len(row['contexto_ambiental']['AMBIENTAL']) == 1
    assert row['metadatos']['agrupacion_descartada']['dispersion_seg'] > 5
    assert _bitacora(db_session, 'AGRUPACION_DESCARTADA', str(row['id_paquetes_inferencia']))[0]['dispersion_seg'] > 5


def test_e6_limite_por_dispositivo_salvo_criticos(client, monkeypatch, hardware):
    from src.telemetry.application.use_cases.inferencia import recibir_evento_edge_use_case as uc
    monkeypatch.setattr(uc, 'LIMITE_EVENTOS_POR_MINUTO', 2)
    normal = _payload(hardware, 'NORMAL')
    assert [client.post('/iot/eventos-edge', json=normal).status_code for _ in range(3)] == [201, 201, 429]
    critico = {**normal, 'severidad': 'CRITICO'}
    assert client.post('/iot/eventos-edge', json=critico).status_code == 201


def test_e7_intento_no_autorizado_queda_como_critical(client, db_session, hardware):
    ajeno = {**_payload(hardware), 'serial': 'serial-ajeno-e7'}
    assert client.post('/iot/eventos-edge', json=ajeno).status_code == 401
    assert client.post('/iot/eventos-edge', json=_payload(hardware), headers={'Authorization': 'Bearer otro'}).status_code == 401
    filas = db_session.execute(text(
        "SELECT entidad_afectada_id, severidad_log, accion_detallada->>'codigo_error' FROM modulo3.bitacora_auditoria_iot "
        "WHERE tipo_evento = 'INTENTO_NO_AUTORIZADO_EVENTO_EDGE' ORDER BY fecha_hora DESC LIMIT 2")).all()
    assert {(f[0], f[1], f[2]) for f in filas} == {
        ('serial-ajeno-e7', 'CRITICAL', 'DISPOSITIVO_NO_AUTORIZADO'),
        (None, 'CRITICAL', 'TOKEN_SERVICIO_INVALIDO'),
    }


# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-177-G57B RF-58: dashboard de 431 sensores en 500 ms, sin aviso E7 dentro del GET |
"""INC-M03-177-G57B (RF-58, CU04 CA-13): el dashboard responde en 500 ms o menos.

QA midió en TEST (431 sensores) un 500 tras 3 min 21 s y un 200 tras 1 min 34 s. Aquí se
siembra un escenario del mismo tamaño en PostgreSQL real, con RLS (rol ``sgpmp_app``), y
se mide el GET con el aviso E7 simulando un SMTP lento. Antes de G57B: 9,2 s la primera
llamada (17 correos síncronos) y ~0,3 s las siguientes.
"""
from __future__ import annotations

import time
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from src.shared import jwt as jwt_module
from src.shared.database import CORREO_USUARIO_SERVICIO, como_sistema, get_db
from src.shared.error_handlers import register_error_handlers
from src.telemetry.infrastructure.adapters import aviso_sin_umbral_background_adapter as bg_mod
from src.telemetry.infrastructure.adapters import aviso_sin_umbral_email_adapter as aviso_mod
from src.telemetry.infrastructure.routers.monitoreo_router import router

pytestmark = pytest.mark.integration
_PROCESAR = bg_mod._procesar_aviso_sin_umbral

SENSORES = 431
AREAS = 9
LECTURAS_POR_SENSOR = 150
SMTP_LENTO_S = 0.5
PRESUPUESTO_S = 0.5  # CA-13: cada refresco del dashboard
# La primera llamada de un proceso nuevo compila SQLAlchemy y las funciones de RLS (una vez por
# proceso y conexión): en el contenedor varía entre 0,5 y 1,6 s. Se imprime, no se acota.


def _sembrar(db) -> int:
    tag = ''.join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:12])
    uid = db.execute(text('SELECT min(id_usuario) FROM modulo1.usuarios')).scalar_one()
    finca = db.execute(text("""INSERT INTO modulo9.fincas(nombre,ubicacion,tamano_h,es_activo,fecha_creacion,fecha_actualizacion)
        VALUES (:n,'{}',10,true,now(),now()) RETURNING id_finca"""), {'n': 'Finca Rendimiento ' + tag}).scalar_one()
    areas = [db.execute(text("""INSERT INTO modulo9.infraestructuras(nombre,id_finca,superficie,es_activo,tipo)
        VALUES (:n,:f,100,true,'Estanque') RETURNING id_infraestructura"""), {'n': f'Area {tag} {chr(97 + i)}', 'f': finca}).scalar_one()
        for i in range(AREAS)]
    especie = db.execute(text("""INSERT INTO modulo9.especies(nombre,descripcion,fecha_creacion,es_activo)
        VALUES (:n,'G57B',now(),true) RETURNING id_especie"""), {'n': 'Especie Rendimiento ' + tag}).scalar_one()
    umbral = db.execute(text("""INSERT INTO modulo9.umbrales_ambientales(id_especie,id_variable_ambiental,unidad_medida,
        valor_min,valor_max,es_activo,fecha_actualizacion,id_usuario)
        VALUES (:e,9,'°C',15,30,true,now(),:u) RETURNING id_umbral_ambiental"""), {'e': especie, 'u': uid}).scalar_one()
    for nivel, a, b in [('normal', 15, 25), ('precaucion', 25, 28), ('critico', 28, 30)]:
        db.execute(text("""INSERT INTO modulo9.niveles_alerta_ambientales(id_umbral_ambiental,nivel,limite_inferior,limite_superior)
            VALUES (:i,:n,:a,:b)"""), {'i': umbral, 'n': nivel, 'a': a, 'b': b})
    for area in areas:
        db.execute(text('INSERT INTO modulo9.infraestructuras_especies(id_infraestructura,id_especie) VALUES (:a,:e)'),
                   {'a': area, 'e': especie})
    dispositivos = [db.execute(text("""INSERT INTO modulo9.dispositivos_iot(serial,descripcion,es_activo,fecha_creacion,
        id_infraestructura,id_tipo_dispositivo) VALUES (:s,'G57B',true,now(),:a,3) RETURNING id_dispositivo_iot"""),
        {'s': f'{tag}-{i}', 'a': area}).scalar_one() for i, area in enumerate(areas)]
    # 431 sensores repartidos en las áreas; un tercio mide humedad (sin umbral → GRIS, E7) y
    # uno de cada cinco arrastra lecturas ERROR_CALIBRACION (la consulta busca la última válida).
    db.execute(text("""
        WITH nuevos AS (
            INSERT INTO modulo9.sensores(id_dispositivo_iot,es_activo,nombre)
            SELECT (:dispositivos)[1 + (g % :n_areas)], true, 'Sensor G57B ' || g
            FROM generate_series(1, :total) g
            RETURNING id_sensores, id_dispositivo_iot
        )
        INSERT INTO modulo9.sensores_areas_asociadas(id_sensor,id_dispositivo_iot,id_infraestructura,punto_instalacion,
            tiene_estado,fecha_asociacion,id_usuario)
        SELECT n.id_sensores, n.id_dispositivo_iot, d.id_infraestructura, 'G57B', true, now() - interval '2 days', :u
        FROM nuevos n JOIN modulo9.dispositivos_iot d USING (id_dispositivo_iot)
    """), {'dispositivos': dispositivos, 'n_areas': AREAS, 'total': SENSORES, 'u': uid})
    db.execute(text("""
        INSERT INTO modulo3.telemetrias(id_sensor,id_variable,id_dispositivo_iot,valor_crudo,valor_ajustado,
            timestamp_captura,timestamp_procesamiento,origen,estado_calidad,metadatos,categoria_variable,unidad_medida,
            nivel_bateria_pct,calidad_senal_rssi,calidad_senal_snr)
        SELECT s.id_sensores,
               CASE WHEN s.id_sensores % 3 = 0 THEN 10 ELSE 9 END,
               s.id_dispositivo_iot, 22, 22,
               clock_timestamp() - make_interval(mins => :lecturas - k + 1),
               clock_timestamp(), 'TIEMPO_REAL',
               (CASE WHEN s.id_sensores % 5 = 0 AND k > 30 THEN 'ERROR_CALIBRACION' ELSE 'LECTURA_VALIDA' END)
                   ::modulo3.enum_telemetria_estado_calidad,
               '{}'::jsonb, 'AMBIENTAL',
               CASE WHEN s.id_sensores % 3 = 0 THEN '%' ELSE '°C' END,
               80, -70, 9
        FROM modulo9.sensores s CROSS JOIN generate_series(1, :lecturas) k
        WHERE s.id_dispositivo_iot = ANY(:dispositivos)
        ORDER BY k, s.id_sensores
    """), {'dispositivos': dispositivos, 'lecturas': LECTURAS_POR_SENSOR})
    # Con estadísticas, como en TEST (autovacuum); sin ellas el plan no es el de un entorno real.
    for tabla in ('modulo3.telemetrias', 'modulo3.estados_actuales_sensores', 'modulo9.sensores',
                  'modulo9.sensores_areas_asociadas', 'modulo3.bitacora_auditoria_iot'):
        db.execute(text(f'ANALYZE {tabla}'))
    db.commit()
    return finca


@pytest.fixture
def escenario(db_session, crear_usuario_db, crear_auth_headers):
    finca = _sembrar(db_session)
    admin = crear_usuario_db(id_rol=1)
    db_session.commit()
    return {'finca': finca, 'headers': crear_auth_headers(admin)}


@pytest.fixture
def smtp_lento(monkeypatch):
    enviados = []

    def enviar(**kw):
        time.sleep(SMTP_LENTO_S)
        enviados.append(kw)

    monkeypatch.setattr(aviso_mod, 'send_email', enviar)
    return enviados


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
        try:
            yield db_session
        finally:
            db_session.execute(text('RESET ROLE'))

    app.dependency_overrides[get_db] = conexion
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def _medir(cliente, headers, veces=4):
    tiempos, respuesta = [], None
    for _ in range(veces):
        inicio = time.perf_counter()
        respuesta = cliente.get('/iot/monitoreo/dashboard', headers=headers)
        tiempos.append(time.perf_counter() - inicio)
        assert respuesta.status_code == 200, respuesta.text
    return tiempos, respuesta.json()


@pytest.fixture
def avisos_diferidos(monkeypatch):
    """TestClient espera a las BackgroundTasks antes de devolver; se difieren para medir solo la respuesta."""
    agendados = []
    monkeypatch.setattr(bg_mod, '_EN_CURSO', set())
    monkeypatch.setattr(bg_mod, '_procesar_aviso_sin_umbral', lambda sensores: agendados.append(sensores))
    return agendados


class _SesionDelTest:
    """La sesión del test hace de sesión de sistema del aviso; no se cierra."""

    def __init__(self, db):
        self._db = db

    def __getattr__(self, nombre):
        return getattr(self._db, nombre)

    def close(self):
        pass


def test_dashboard_de_431_sensores_responde_en_500_ms(cliente, escenario, smtp_lento, avisos_diferidos):
    tiempos, datos = _medir(cliente, escenario['headers'])
    print(f'\nG57B tiempos GET /iot/monitoreo/dashboard: {[round(t, 3) for t in tiempos]} s; correos={len(smtp_lento)}')
    assert datos['total'] >= SENSORES and len(datos['sensores']) == 50
    assert sum(datos['conteo_semaforo'].values()) == datos['total']
    assert max(tiempos[1:]) <= PRESUPUESTO_S
    # Ningún correo dentro del request; el aviso quedó agendado una sola vez por sensor.
    assert smtp_lento == []
    agendados = [s.id_sensor for lote in avisos_diferidos for s in lote]
    sin_umbral = [s['id_sensor'] for s in datos['sensores'] if s['sin_umbral']]
    assert sin_umbral and sorted(agendados) == sorted(sin_umbral)


def test_el_aviso_en_segundo_plano_escribe_la_bitacora_y_envia(cliente, db_session, escenario, smtp_lento,
                                                                avisos_diferidos, monkeypatch):
    assert cliente.get('/iot/monitoreo/dashboard', headers=escenario['headers']).status_code == 200
    [lote] = avisos_diferidos
    monkeypatch.setattr(bg_mod, 'sesion_sistema', lambda: _SesionDelTest(db_session))
    _PROCESAR(lote)

    with como_sistema(db_session):
        admins = len(db_session.execute(aviso_mod._SQL_ADMINISTRADORES,
                                        {'correo_servicio': CORREO_USUARIO_SERVICIO}).fetchall())
    registrados = db_session.execute(text(
        "SELECT count(*) FROM modulo3.bitacora_auditoria_iot WHERE tipo_evento = 'VARIABLE_SIN_UMBRAL' "
        "AND entidad_afectada_id = ANY(:ids)"), {'ids': [str(s.id_sensor) for s in lote]}).scalar_one()
    assert registrados == len(lote) and len(smtp_lento) == len(lote) * admins
    assert bg_mod._EN_CURSO == set()

    # Un refresco posterior vuelve a agendar, pero la bitácora (24 h) evita repetir el correo.
    enviados = len(smtp_lento)
    assert cliente.get('/iot/monitoreo/dashboard', headers=escenario['headers']).status_code == 200
    _PROCESAR(avisos_diferidos[-1])
    assert len(smtp_lento) == enviados

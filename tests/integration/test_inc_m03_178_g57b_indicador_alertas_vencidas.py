# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-178-G57B RF-57: el indicador de vencidas sube al vencer una alerta (TC-M03-N46) |
"""INC-M03-178-G57B (RF-57 Salida 3, TC-M03-N46) con PostgreSQL real, RLS y JWT.

Una alerta CRITICO sin atender pasa a VENCIDA con el worker real de DEV-31 y el indicador
``alertas_vencidas_sin_atencion`` sube en GET /iot/alertas/indicadores y en el dashboard.
"""
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from src.shared import jwt as jwt_module
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.telemetry.application.use_cases.alertas.vencer_alertas_sla_use_case import VencerAlertasSlaUseCase
from src.telemetry.infrastructure.repositories.alerta_repository import SqlAlchemyAlertaRepository
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import (
    SqlAlchemyBitacoraAuditoriaIotRepository,
)
from src.telemetry.infrastructure.routers import alerta_router, monitoreo_router

_spec = importlib.util.spec_from_file_location('g57b_base', Path(__file__).with_name('test_dev05_ingesta_bplus_postcommit.py'))
h = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h)
modelos = h.modelos
pytestmark = pytest.mark.integration


def _alerta(db, area, severidad='CRITICO', minutos_atras=6, tipo='ESTRES_TERMICO'):
    return db.execute(text("""
        INSERT INTO modulo3.alertas (tipo_alerta, severidad, estado_alerta, origen_evento, fecha_evento,
                                     fecha_generacion, tipo_variable, id_infraestructura)
        VALUES (CAST(:t AS modulo3.enum_tipo_alerta), CAST(:s AS modulo3.enum_buffer_nivel_severidad), 'ACTIVA',
                'EDGE', now(), now() - make_interval(mins => :m), 'TEMPERATURA', :a)
        RETURNING id_alerta
    """), {'t': tipo, 's': severidad, 'm': minutos_atras, 'a': area}).scalar_one()


def _pasar(db, id_alerta, *estados):
    for estado in estados:
        db.execute(text("UPDATE modulo3.alertas SET estado_alerta = CAST(:e AS modulo3.enum_estado_alerta) "
                        "WHERE id_alerta = :a"), {'e': estado, 'a': id_alerta})


@pytest.fixture
def contexto(db_session, crear_usuario_db, crear_auth_headers):
    db = db_session
    propio, ajeno = h.hardware(db), h.hardware(db)
    finca = db.execute(text('SELECT id_finca FROM modulo9.infraestructuras WHERE id_infraestructura = :a'),
                       {'a': propio['area']}).scalar_one()
    id_rol = db.execute(text("SELECT id_rol FROM modulo1.roles WHERE nombre_rol = 'Productor'")).scalar_one()
    productor = crear_usuario_db(id_rol=id_rol)
    numero = db.execute(text('SELECT COALESCE(max(id_usuario_finca), 0) + 1 FROM modulo9.usuarios_fincas')).scalar_one()
    db.execute(text('INSERT INTO modulo9.usuarios_fincas(id_usuario_finca, id_usuario, id_finca, es_activo) '
                    'VALUES (:i, :u, :f, true)'), {'i': numero, 'u': productor['id_usuario'], 'f': finca})
    db.commit()
    return {'area': propio['area'], 'ajena': ajeno['area'], 'headers': crear_auth_headers(productor)}


@pytest.fixture
def cliente(db_session, monkeypatch):
    monkeypatch.setattr(jwt_module, '_SECRET_KEY', 'sgpmp-integration-tests-only')
    monkeypatch.setattr(jwt_module, '_EXPIRE_HOURS', 8)
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(alerta_router.router)
    app.include_router(monitoreo_router.router)

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


def _indicadores(cliente, ctx, **params):
    r = cliente.get('/iot/alertas/indicadores', params={'id_infraestructura': ctx['area'], **params},
                    headers=ctx['headers'])
    assert r.status_code == 200, r.text
    return r.json()


def _vencer(db):
    VencerAlertasSlaUseCase(db, SqlAlchemyAlertaRepository(db), SqlAlchemyBitacoraAuditoriaIotRepository(db)
                            ).execute(datetime.now(timezone.utc))


def test_n46_la_alerta_vencida_sube_el_indicador_en_la_ruta_y_en_el_dashboard(cliente, db_session, contexto):
    _alerta(db_session, contexto['area'])
    db_session.commit()
    antes = _indicadores(cliente, contexto)
    assert antes['alertas_vencidas_sin_atencion'] == 0
    assert antes['alertas_activas_total'] == 1 and antes['alertas_criticas_activas'] == 1
    assert antes['alertas_por_tipo'] == {'ESTRES_TERMICO': 1}

    _vencer(db_session)

    despues = _indicadores(cliente, contexto)
    assert despues['alertas_vencidas_sin_atencion'] == 1
    assert despues['alertas_activas_total'] == 0 and despues['alertas_por_tipo'] == {}
    tablero = cliente.get(f"/iot/monitoreo/dashboard/{contexto['area']}", headers=contexto['headers'])
    assert tablero.status_code == 200, tablero.text
    assert tablero.json()['alertas_vencidas_sin_atencion'] == 1


def test_alcance_tecnicas_y_vencida_tras_atencion_no_cuentan(cliente, db_session, contexto):
    _alerta(db_session, contexto['area'])
    _alerta(db_session, contexto['ajena'])                    # otra finca: fuera del alcance del Productor
    _alerta(db_session, contexto['area'], tipo='TECNICA')    # RF-60: técnica, no operativa
    atendida = _alerta(db_session, contexto['area'], minutos_atras=1)
    _pasar(db_session, atendida, 'EN_ATENCION', 'VENCIDA')   # vencida, pero sí fue reconocida
    db_session.commit()
    _vencer(db_session)

    sin_area = cliente.get('/iot/alertas/indicadores', headers=contexto['headers']).json()
    assert sin_area['alertas_vencidas_sin_atencion'] == 1
    assert _indicadores(cliente, contexto)['alertas_vencidas_sin_atencion'] == 1


def test_resolucion_falsos_positivos_y_rango_de_fechas(cliente, db_session, contexto):
    resuelta = _alerta(db_session, contexto['area'], severidad='LEVE', minutos_atras=30)
    _pasar(db_session, resuelta, 'EN_ATENCION', 'RESUELTA')
    for _ in range(3):
        _pasar(db_session, _alerta(db_session, contexto['area'], severidad='LEVE', minutos_atras=1), 'DESCARTADA')
    db_session.commit()

    datos = _indicadores(cliente, contexto)
    assert datos['alertas_resueltas'] == 1 and datos['alertas_descartadas'] == 3
    assert datos['tasa_falsos_positivos'] == 0.75
    assert 29 <= datos['tiempo_promedio_resolucion_min'] <= 31

    futuro = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    vacio = _indicadores(cliente, contexto, fecha_desde=futuro)
    assert vacio['alertas_resueltas'] == 0 and vacio['tasa_falsos_positivos'] is None
    assert vacio['tiempo_promedio_resolucion_min'] is None

    pasado = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    r = cliente.get('/iot/alertas/indicadores', params={'fecha_desde': futuro, 'fecha_hasta': pasado},
                    headers=contexto['headers'])
    assert r.status_code == 400 and r.json()['error_code'] == 'RANGO_FECHAS_INVALIDO'

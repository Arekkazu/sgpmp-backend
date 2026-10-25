# | Fecha      | Nombre   | Que se hizo                                         |
# |------------|----------|-----------------------------------------------------|
# | 2026-10-25 | Arekkazu | INC-M03-134-G192 RF-62: evaluar calidad de visión por HTTP |
"""INC-M03-134-G192 (RF-62): flujo de dos pasos de la calidad de visión.

1. ``POST /iot/telemetria/vision`` guarda la observación sin evaluarla.
2. ``POST /iot/calidad/vision/{id}/evaluar`` (JWT + RBAC recurso 38, Ejecutar)
   aplica el índice ponderado de AIOT-SPEC-01 y lo persiste.
"""
from __future__ import annotations

import importlib.util
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import text

from src.configuration.application.use_cases.configuracion_global.configurar_parametros_mlops_use_case import (
    ConfigurarParametrosMLOpsUseCase,
)
from src.configuration.domain.entities.parametros_heartbeat import COBERTURA, DURACION, VENTANAS
from src.configuration.domain.entities.parametros_vision import PREDETERMINADOS_VISION
from src.configuration.infrastructure.repositories.configuracion_global_repository import (
    SqlAlchemyConfiguracionGlobalRepository,
)
from src.prediction.infrastructure.repositories.parametros_mlops_repository import SqlAlchemyParametrosMLOpsRepository

_spec = importlib.util.spec_from_file_location('g192_vision_base', Path(__file__).with_name('test_dev07_vision_d4.py'))
h = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h)
modelos = h.modelos
pytestmark = pytest.mark.integration


@pytest.fixture
def cliente(client, integration_app):
    from src.telemetry.infrastructure.routers.calidad_router import router
    if not any(getattr(r, 'path', '') == '/iot/calidad/vision/{id_observacion_vision}/evaluar' for r in integration_app.routes):
        integration_app.include_router(router)
    return client


@pytest.fixture
def observacion(db_session, modelos):
    """Una observación D4 ingerida (sin evaluar) y la política D de RF-62 sembrada."""
    equipo = h.hardware(db_session)
    usuario = db_session.execute(text('SELECT min(id_usuario) FROM modulo1.usuarios')).scalar_one()
    writer = ConfigurarParametrosMLOpsUseCase(
        db_session, SqlAlchemyParametrosMLOpsRepository(db_session), SqlAlchemyConfiguracionGlobalRepository(db_session))
    writer.execute(PREDETERMINADOS_VISION, usuario)
    writer.execute({VENTANAS: 3, COBERTURA: .30, DURACION: 60}, usuario)
    dto = h.ObservacionVisionD4DTO(**h.sobre(equipo))
    h.IngerirObservacionesVisionUseCase(
        db_session, h.SqlAlchemyObservacionVisionRepository(db_session), h.DispositivoM09Adapter(db_session)).execute(dto)
    fila = h.filas(db_session, equipo)[0]
    assert fila['fecha_evaluacion_calidad'] is None
    return fila['id_observacion_vision']


def test_administrador_evalua_y_queda_persistido(cliente, db_session, observacion, crear_usuario_db, crear_auth_headers):
    headers = crear_auth_headers(crear_usuario_db(id_rol=1))
    r = cliente.post(f'/iot/calidad/vision/{observacion}/evaluar', headers=headers)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    # 100 × (0.40×0.95 + 0.35×24/25 + 0.25×(1 − 1/5)) = 38 + 33.6 + 20
    assert Decimal(str(cuerpo['indice_calidad_vision'])) == Decimal('91.60')
    assert (cuerpo['clasificacion_calidad'], cuerpo['apto_para_ia'], cuerpo['apto_para_nic41']) == ('OPTIMA', True, False)
    assert cuerpo['flags_detectados']['tracking_inestable']['activo'] is False
    fila = db_session.execute(text(
        'SELECT indice_calidad_vision, es_apto_para_ia, fecha_evaluacion_calidad '
        'FROM modulo3.observaciones_vision WHERE id_observacion_vision = :id'), {'id': observacion}).one()
    assert fila[0] == Decimal('91.60') and fila[1] is True and fila[2] is not None

    # Idempotente: una segunda llamada devuelve la misma evaluación.
    otra = cliente.post(f'/iot/calidad/vision/{observacion}/evaluar', headers=headers).json()
    assert otra['fecha_evaluacion_calidad'] == cuerpo['fecha_evaluacion_calidad']


def test_productor_sin_permiso_de_ejecutar(cliente, observacion, crear_usuario_db, crear_auth_headers):
    r = cliente.post(f'/iot/calidad/vision/{observacion}/evaluar', headers=crear_auth_headers(crear_usuario_db(id_rol=2)))
    assert r.status_code == 403, r.text


def test_observacion_inexistente(cliente, crear_usuario_db, crear_auth_headers):
    r = cliente.post('/iot/calidad/vision/999999999/evaluar', headers=crear_auth_headers(crear_usuario_db(id_rol=1)))
    assert r.status_code == 404, r.text
    assert r.json()['error_code'] == 'OBSERVACION_VISION_NO_ENCONTRADA'

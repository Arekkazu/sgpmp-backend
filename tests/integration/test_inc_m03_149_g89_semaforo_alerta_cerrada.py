# | Fecha      | Nombre   | Que se hizo                                                  |
# |------------|----------|--------------------------------------------------------------|
# | 2026-10-25 | Arekkazu | INC-M03-149-G89 RF-58: semáforo tras resolver o descartar alerta |
"""INC-M03-149-G89 (RF-58): al resolver o descartar una alerta no crítica el sensor
volvía a quedar sin alerta pero en AMARILLO, aunque su lectura vigente fuera normal.

El trigger ``fn_sincronizar_alerta_en_sensor`` sube el color al crear la alerta y
al cerrarla solo limpia ``id_alerta``. ``ActualizarEstadoAlertaUseCase`` recalcula
el color con la última lectura válida y las alertas que sigan abiertas.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text

from src.telemetry.application.use_cases.alertas.actualizar_estado_alerta_use_case import ActualizarEstadoAlertaUseCase
from src.telemetry.domain.entities.alerta import AmbitoAlerta
from src.telemetry.infrastructure.dto.actualizar_estado_alerta_dto import ActualizarEstadoAlertaDTO
from src.telemetry.infrastructure.repositories.alerta_repository import SqlAlchemyAlertaRepository
from src.telemetry.infrastructure.repositories.historico_estado_alerta_repository import (
    SqlAlchemyHistoricoEstadoAlertaRepository,
)
from src.telemetry.infrastructure.workers.postcommit_worker import recalcular_semaforo_sensor

_spec = importlib.util.spec_from_file_location('g89_base', Path(__file__).with_name('test_dev41_alertas_telemetria.py'))
h = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h)
modelos = h.modelos
pytestmark = pytest.mark.integration


def _estado(db, sensor):
    return tuple(db.execute(text(
        'SELECT estado_semaforo, id_alerta FROM modulo3.estados_actuales_sensores WHERE id_sensor = :s'),
        {'s': sensor}).one())


def _alerta(db, ctx, severidad):
    id_alerta = db.execute(text(
        "INSERT INTO modulo3.alertas (tipo_alerta, severidad, origen_evento, fecha_evento, tipo_variable, id_sensor) "
        "VALUES ('ESTRES_TERMICO', CAST(:sev AS modulo3.enum_buffer_nivel_severidad), 'BACKEND', now(), "
        "'TEMPERATURA', :s) RETURNING id_alerta"), {'sev': severidad, 's': ctx['sensor']}).scalar_one()
    db.commit()
    return id_alerta


def _cambiar(db, id_alerta, *estados, recalcular=True):
    caso = ActualizarEstadoAlertaUseCase(
        db, SqlAlchemyAlertaRepository(db), SqlAlchemyHistoricoEstadoAlertaRepository(db), AmbitoAlerta.OPERATIVA,
        recalcular_semaforo=(lambda s: recalcular_semaforo_sensor(db, s)) if recalcular else None)
    usuario = db.execute(text('SELECT min(id_usuario) FROM modulo1.usuarios')).scalar_one()
    for estado in estados:
        caso.execute(id_alerta, ActualizarEstadoAlertaDTO(nuevo_estado=estado, motivo='Prueba G89'), usuario)


@pytest.fixture
def sensor_verde(db_session):
    ctx = h.preparar(db_session)
    h.ingresar(db_session, ctx, 25)  # rango normal 20–30
    h.worker(db_session).execute()
    assert _estado(db_session, ctx['sensor']) == ('VERDE', None)
    return ctx


@pytest.mark.parametrize('severidad, estados', [
    ('LEVE', ('EN_ATENCION', 'RESUELTA')),
    ('MODERADO', ('DESCARTADA',)),
])
def test_cerrar_la_alerta_devuelve_el_color_de_la_lectura(db_session, sensor_verde, severidad, estados):
    id_alerta = _alerta(db_session, sensor_verde, severidad)
    assert _estado(db_session, sensor_verde['sensor']) == ('AMARILLO', id_alerta)
    _cambiar(db_session, id_alerta, *estados)
    assert _estado(db_session, sensor_verde['sensor']) == ('VERDE', None)


def test_sin_recalculo_queda_el_defecto_reportado(db_session, sensor_verde):
    id_alerta = _alerta(db_session, sensor_verde, 'MODERADO')
    _cambiar(db_session, id_alerta, 'DESCARTADA', recalcular=False)
    assert _estado(db_session, sensor_verde['sensor']) == ('AMARILLO', None)


def test_otra_alerta_abierta_conserva_el_amarillo(db_session, sensor_verde):
    primera = _alerta(db_session, sensor_verde, 'LEVE')
    _alerta(db_session, sensor_verde, 'MODERADO')
    _cambiar(db_session, primera, 'DESCARTADA')
    assert _estado(db_session, sensor_verde['sensor'])[0] == 'AMARILLO'

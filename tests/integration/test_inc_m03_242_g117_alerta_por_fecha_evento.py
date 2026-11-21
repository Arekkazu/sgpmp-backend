# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-10-31 | Claude | INC-M03-242-G117 RF-59: la alerta entra por la fecha de su evento |
"""INC-M03-242-G117 (#883, TC-M03-235): la alerta 21 (DESCARTADA, sensor 1, fecha_evento
2026-05-12T16:28:05Z) no aparecía en el historial del 11 al 13/05 con incluir_alertas=true:
el periodo se comparaba con fecha_generacion, que es posterior. RF-59 Salida 5 / Fase 4:
alertas que *ocurrieron* en el periodo, en cualquier estado.
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import text

from src.telemetry.domain.entities.monitoreo import FiltrosHistorial
from src.telemetry.infrastructure.repositories.historial_telemetria_repository import (
    SqlAlchemyHistorialTelemetriaRepository,
)

pytestmark = pytest.mark.integration

_SENSOR = 900021


@pytest.fixture
def alerta_descartada(db_session):
    db_session.execute(text("SET LOCAL session_replication_role = replica"))
    id_alerta = db_session.execute(text(
        "INSERT INTO modulo3.alertas (tipo_alerta, severidad, origen_evento, fecha_evento, fecha_generacion, "
        "estado_alerta, tipo_variable, id_sensor, id_telemetria) VALUES ('ESTRES_TERMICO', 'LEVE', 'EDGE', "
        "'2026-05-12 16:28:05Z', '2026-10-29 09:00Z', 'DESCARTADA', 'TEMPERATURA_AMBIENTAL', :s, 999999931) "
        "RETURNING id_alerta"), {"s": _SENSOR}).scalar_one()
    db_session.execute(text("SET LOCAL session_replication_role = origin"))
    return id_alerta


def test_alerta_del_periodo_generada_despues_aparece(db_session, alerta_descartada):
    alertas = SqlAlchemyHistorialTelemetriaRepository(db_session).alertas_correlacionadas(FiltrosHistorial(
        fecha_inicio=date(2026, 5, 11), fecha_fin=date(2026, 5, 13), incluir_alertas=True, sensor_id=_SENSOR))

    encontrada = next(a for a in alertas if a.id_alerta == alerta_descartada)
    assert encontrada.estado_final == 'DESCARTADA'
    assert encontrada.variable_afectada == 'TEMPERATURA_AMBIENTAL'


def test_periodo_de_la_generacion_no_la_trae(db_session, alerta_descartada):
    alertas = SqlAlchemyHistorialTelemetriaRepository(db_session).alertas_correlacionadas(FiltrosHistorial(
        fecha_inicio=date(2026, 10, 28), fecha_fin=date(2026, 10, 30), incluir_alertas=True, sensor_id=_SENSOR))

    assert alerta_descartada not in {a.id_alerta for a in alertas}
